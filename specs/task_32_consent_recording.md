# Task 32: Consent Recording

> Persist a timestamped, versioned consent record in Supabase every time a user agrees to the Terms of Service and Privacy Policy during sign-up.

## 1. Task Overview
- **Summary:** When a user completes sign-up and ticks "I agree to the Terms of Service and Privacy Policy", write a row to a `consents` table recording the user, timestamp, terms version, and IP address. This provides a legally defensible audit trail for GDPR and similar regulations.
- **Background:** The consent checkbox currently exists only in React state and is never persisted. If a regulator or user asks when and to which version of the terms they consented, we have no record. The sign-up flow is in `frontend/src/app/(auth)/sign-up/page.tsx`, which calls `supabase.auth.signUp()`.
- **Primary Owner:** Cristian

## 2. Objectives & Success Criteria
- **Goals:**
  - Every successful sign-up inserts one row into `public.consents` with user ID, agreed timestamp, terms version string, and IP address.
  - The terms version is a date string (e.g. `"2026-05-21"`) managed as a constant in the frontend so it is bumped intentionally when terms change.
  - Consent insert happens server-side (Next.js Route Handler or Supabase trigger) so the client cannot forge or omit it.
- **Non-Goals:**
  - Re-consent flows for existing users when terms change (future task).
  - Storing granular per-clause consent (overkill for now).
  - Marketing consent — this covers T&C / Privacy Policy only.
- **Definition of Done:**
  - `public.consents` table exists in Supabase with the schema below.
  - Row-Level Security (RLS) is enabled: users can read their own row; no client can insert directly (insert goes through the service role only).
  - After a successful sign-up in local dev, a row appears in the `consents` table.
  - A new sign-up without `agreed = true` (if somehow reached) does not insert a row and does not block sign-up (consent insert is best-effort, non-blocking).

## 3. System Context
- **Repositories / Services Affected:**
  - `frontend/src/app/(auth)/sign-up/page.tsx` — `SignUpForm`, `handleSubmit`
  - `frontend/src/app/api/auth/consent/route.ts` — new Route Handler (server-side insert)
  - Supabase project — new table + RLS policy + optional trigger
- **Architecture Notes:**
  - `supabase.auth.signUp()` runs client-side; user ID is available in the response.
  - The consent insert must use the **service role key** (never the anon key) to bypass RLS and insert on behalf of the new user whose session is not yet fully established.
  - The service role key is already available server-side in `SUPABASE_SERVICE_ROLE_KEY` (or similar env var — check `.env.local`). It must never be sent to the browser.
  - IP address: captured from the `x-forwarded-for` or `x-real-ip` request header inside the Route Handler. Store the first (client) IP only.

## 4. Constraints & Requirements
- **Technical Constraints:**
  - Next.js 16 App Router, TypeScript, Supabase JS v2 (`@supabase/supabase-js`).
  - Service role client is created with `createClient(url, serviceRoleKey)` — not the SSR helper.
  - Consent insert failure must not block sign-up or show an error to the user (fire-and-forget from the frontend perspective, but log errors server-side).
- **Security / Compliance:**
  - Service role key only used server-side inside the Route Handler.
  - RLS: `SELECT` allowed for `auth.uid() = user_id`; no `INSERT`/`UPDATE`/`DELETE` via RLS (service role bypasses RLS).
  - IP address is personal data under GDPR — document its purpose (fraud prevention / consent proof) in a comment in the migration.

## 5. Inputs & Resources
- **Artifacts:**
  - `frontend/src/app/(auth)/sign-up/page.tsx` — existing sign-up form
  - `frontend/src/utils/supabase/client.ts` — browser Supabase client
  - Supabase dashboard → SQL Editor for running the migration
- **Assumptions:**
  - `SUPABASE_SERVICE_ROLE_KEY` is available as a server-only env var (not prefixed `NEXT_PUBLIC_`).
  - The terms version constant starts at `"2026-05-21"` and is stored in `frontend/src/lib/terms.ts` (new file, one export).

## 6. Implementation Plan

### Step 1 — Database migration
Run in Supabase SQL Editor:

```sql
create table public.consents (
  id            uuid primary key default gen_random_uuid(),
  user_id       uuid not null references auth.users(id) on delete cascade,
  terms_version text not null,
  agreed_at     timestamptz not null default now(),
  -- IP address stored for consent proof / fraud prevention (GDPR Art. 7 accountability).
  ip_address    text
);

alter table public.consents enable row level security;

-- Users can read their own consent record; no client-side writes allowed.
create policy "users can view own consents"
  on public.consents for select
  using (auth.uid() = user_id);
```

### Step 2 — Terms version constant
Create `frontend/src/lib/terms.ts`:

```ts
export const TERMS_VERSION = "2026-05-21";
```

Bump this string whenever T&C or Privacy Policy content changes materially.

### Step 3 — Route Handler (server-side insert)
Create `frontend/src/app/api/auth/consent/route.ts`:

```ts
import { createClient } from "@supabase/supabase-js";
import { NextResponse } from "next/server";
import { TERMS_VERSION } from "@/lib/terms";

export async function POST(request: Request) {
  const { userId } = await request.json();
  if (!userId) return NextResponse.json({ error: "missing userId" }, { status: 400 });

  const ip =
    request.headers.get("x-forwarded-for")?.split(",")[0].trim() ??
    request.headers.get("x-real-ip") ??
    null;

  const supabase = createClient(
    process.env.NEXT_PUBLIC_SUPABASE_URL!,
    process.env.SUPABASE_SERVICE_ROLE_KEY!
  );

  const { error } = await supabase.from("consents").insert({
    user_id: userId,
    terms_version: TERMS_VERSION,
    ip_address: ip,
  });

  if (error) {
    console.error("[consent] insert failed", error);
    // Non-blocking: sign-up already succeeded; do not surface this to the user.
  }

  return NextResponse.json({ ok: true });
}
```

### Step 4 — Call from sign-up form
In `frontend/src/app/(auth)/sign-up/page.tsx`, after a successful `signUp` call:

```ts
const { data, error } = await supabase.auth.signUp({ email, password, ... });

if (!error && data.user) {
  // Fire-and-forget — don't await, don't block the UX
  fetch("/api/auth/consent", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ userId: data.user.id }),
  }).catch(() => {}); // silent on network error
}
```

## 7. Testing & Validation
- **Manual test:** Sign up a new user in local dev → open Supabase Table Editor → `consents` table should have one row with the correct `user_id`, `terms_version`, and a recent `agreed_at`.
- **Negative test:** Check that calling `POST /api/auth/consent` without a `userId` body returns 400 and writes nothing.
- **RLS test:** Sign in as the new user, run `select * from consents` via the Supabase JS client (anon key) — should return the user's own row only.

## 8. Risk Management
- **Known Risks:**
  - `data.user.id` may be `null` if email confirmation is required (Supabase returns the user object but with `identities: []` until confirmed). In that case the consent insert still works — user ID is present even before confirmation.
  - Service role key accidentally leaking client-side: mitigated by keeping it in a non-`NEXT_PUBLIC_` env var and only using it inside `app/api/`.
- **Mitigations:** Consent insert is non-blocking and logged server-side; sign-up UX is unaffected by insert failures.

## 9. Delivery & Handoff
- **Deliverables:**
  - Supabase migration applied (SQL above).
  - `frontend/src/lib/terms.ts` created.
  - `frontend/src/app/api/auth/consent/route.ts` created.
  - `frontend/src/app/(auth)/sign-up/page.tsx` updated to fire consent call.
- **Post-Delivery:** Verify row appears in Supabase Table Editor after a test sign-up. Delete the test user and its consent row afterwards.

## 11. Appendix
- **Glossary:**
  - *Terms version* — a date string (`YYYY-MM-DD`) identifying the published version of the T&C + Privacy Policy in effect at the time of consent.
  - *Service role key* — a Supabase secret key that bypasses RLS; server-side only.
- **Change Log:**
  - 2026-05-21 — Initial spec created.
