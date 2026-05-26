# Task 22: Web User Data Wiring

**Status: ✅ COMPLETED** (2026-05-26)

> Connect the web dashboard to live Supabase data: real user identity, Traveler DNA tags, credits balance, and a one-time server-side welcome-credits grant with first-login modal.

## 1. Task Overview

- **Summary:** Replace all mock constants in the dashboard (hardcoded name, DNA tags, credits) with live data fetched from Supabase. Implement a server-side welcome-credits grant triggered by the user on their first dashboard visit, controlled by the `DEFAULT_USER_CREDITS` env var.
- **Background:** The dashboard (`/dashboard`) was implemented with mock data (`src/lib/dashboard-data.ts`). The DB now has the `auth_id` bridge on `public.users`, RLS policies, and the `on_auth_user_created` trigger that auto-provisions `users + user_profiles + credits` rows on signup. The only missing pieces are: the live data hook, the welcome-grant API, and wiring them into the UI.
- **Primary Owner:** Cristian

## 2. Objectives & Success Criteria

- **Goals:**
  - ProfileDropdown shows real name, email, DNA tags, and credit balance for the logged-in user.
  - On first dashboard visit (credits.welcome_credits_claimed_at IS NULL), a modal appears.
  - User clicks "Claim credits" → Route Handler validates session, updates credits atomically, returns balance.
  - Modal cannot be triggered more than once per account (DB timestamp guards it).
  - Credit amount is controlled by `DEFAULT_USER_CREDITS` env var (server-side only; same name as backend).
  - New auth signups automatically get `users + user_profiles + credits` rows via the DB trigger.
- **Non-Goals:**
  - Wiring trip data, chat history, or map to live data (separate future task).
  - Account settings page (future task).
  - Promo code UI (Telegram-only for now).

## 3. System Context

- **Repositories / Services Affected:**
  - `frontend/src/utils/supabase/service.ts` — new service-role Supabase client (server-side only)
  - `frontend/src/app/api/credits/welcome-grant/route.ts` — new Route Handler
  - `frontend/src/hooks/useUserProfile.ts` — new client hook
  - `frontend/src/components/dashboard/WelcomeGrantModal.tsx` — new component
  - `frontend/src/components/dashboard/ProfileDropdown.tsx` — accept props, remove internal fetch
  - `frontend/src/components/dashboard/TopNav.tsx` — receive and forward `UserProfile`
  - `frontend/src/components/dashboard/DashboardShell.tsx` — call hook, render modal
  - `frontend/.env.local` — add `SUPABASE_SERVICE_ROLE_KEY`, `DEFAULT_USER_CREDITS`
  - Supabase DB — all changes already applied (see `supabase/` directory)

- **Architecture Notes:**
  - Data flows top-down: `DashboardShell` owns the `useUserProfile` call and passes the result as props. No component fetches independently.
  - The Route Handler uses the service role key to bypass RLS for the credits UPDATE. The user's session is validated with the regular server client first.
  - `DEFAULT_USER_CREDITS` has no `NEXT_PUBLIC_` prefix — the client never sees the raw config value until the API responds.
  - The welcome grant is idempotent: the UPDATE only fires if `welcome_credits_claimed_at IS NULL`, so concurrent requests can't double-grant.

## 4. DB Prerequisites (all already applied)

| Change | Applied |
|---|---|
| `public.users.auth_id` column (FK → auth.users) | ✅ 2026-05-25 |
| `public.credits.welcome_credits_claimed_at` column | ✅ 2026-05-26 |
| `handle_new_auth_user` trigger + function | ✅ 2026-05-26 |
| RLS policies (users_self, profiles_self, credits_self_read) | ✅ 2026-05-25 |

## 5. Implementation Plan

### 5.1 `src/utils/supabase/service.ts`
Server-side Supabase client using `SUPABASE_SERVICE_ROLE_KEY`. Bypasses RLS.
Import only from Route Handlers and Server Components — never from client components.

### 5.2 `POST /api/credits/welcome-grant`
1. Create server Supabase client, get `auth.uid()`.
2. Find `public.users WHERE auth_id = uid` → get `public_user_id`.
3. With service client: `UPDATE credits SET balance=$N, initial_grant=$N, welcome_credits_claimed_at=now() WHERE user_id=$id AND welcome_credits_claimed_at IS NULL RETURNING balance`.
4. If 0 rows updated → `{ status: 'already_claimed' }`.
5. Return `{ status: 'granted', balance: N }`.

### 5.3 `useUserProfile` hook
Single Supabase query via the publishable key + session:
```
users (name) → user_profiles (profile_data.tags) + credits (balance, initial_grant, welcome_credits_claimed_at)
```
Also calls `supabase.auth.getUser()` for email.
Returns `{ name, email, initials, dnaTags, balance, initialGrant, welcomeClaimedAt, loading }`.

### 5.4 `WelcomeGrantModal`
- Rendered by `DashboardShell` when `welcomeClaimedAt === null && !loading`.
- Calls `POST /api/credits/welcome-grant` on confirm.
- Shows loading state; on success updates parent state via `onGranted(balance)` callback.
- Dismissal not allowed — shows until claimed (prevents accidental skip of free credits).

### 5.5 Prop drilling
`DashboardShell` → `DesktopShell` / `MobileShell` → `TopNav` → `ProfileDropdown`.
ProfileDropdown no longer fetches its own data; it receives `userProfile` as a prop.

## 6. Environment Variables

| Variable | Location | Purpose |
|---|---|---|
| `SUPABASE_SERVICE_ROLE_KEY` | `.env.local` + Vercel (server) | Bypass RLS in Route Handler |
| `DEFAULT_USER_CREDITS` | `.env.local` + Vercel (server) | Welcome grant amount (default: 500, matches backend) |
| `NEXT_PUBLIC_SUPABASE_URL` | already set | Supabase project URL |
| `NEXT_PUBLIC_SUPABASE_PUBLISHABLE_KEY` | already set | Browser-safe key |

## 7. Security Notes

- `SUPABASE_SERVICE_ROLE_KEY` must never appear in client bundles. Use only in Route Handlers / Server Components. Verify with `NEXT_PUBLIC_` prefix check.
- The welcome grant UPDATE uses `WHERE welcome_credits_claimed_at IS NULL` as the atomic guard — no separate SELECT needed.
- Session is validated with `supabase.auth.getUser()` (JWT server-side check) before any DB write.

## 8. Definition of Done

- [ ] New auth user signs up → `public.users + user_profiles + credits` rows created automatically.
- [ ] Dashboard loads → ProfileDropdown shows real name, email, DNA tags (or CTA if empty), credit balance.
- [ ] First login → WelcomeGrantModal appears; claim succeeds; balance in ProfileDropdown updates.
- [ ] Second visit → modal does not appear; balance reflects claimed amount.
- [ ] `DEFAULT_USER_CREDITS` change in env → new users get the updated amount.
- [ ] `npx tsc --noEmit` passes with zero errors.
