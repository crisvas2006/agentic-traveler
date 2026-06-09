# Task 23 — Account Settings Page

**Status:** ✅ Completed

## Goal
Implement the Account Settings page from the `account-settings.jsx` design prototype
(`aletheia-travel/project/account-settings.jsx` from the claude.ai/design handoff).

## Route
`/settings` — standalone page with its own nav, **not** nested under `/dashboard`.

## Sections (in order)

### 01 · Profile
- **Avatar** — gradient initials circle (`linear-gradient(135deg, #f59e0b, #ec4899)`)
- **Full name** — inline editable: click/pencil → input with Save / Cancel / ⏎ / Esc. Calls `UPDATE users SET name = $1 WHERE auth_id = auth.uid()`.
- **Email** — read-only, Verified badge (emerald)
- **Traveler DNA tags** — read-only chips from `user_profiles.profile_data.tags`. "Re-take quiz" link (stub).

### 02 · Credits & Plan
- **Balance widget** — big `balance` number, two-stat strip: Remaining + Used so far (`credits.total_spent`)
- **Top up credits** — stub button (future billing integration)
- **Promo code** — dashed button expands inline input. POST `/api/credits/redeem-promo`.
- **Meta column** — Initial credit claimed (`welcome_credits_claimed_at`), Lifetime credits used (`total_spent`), Renewal (copy)

### 03 · Account Info
- Account created (`users.created_at`)
- Last sign-in (`auth.users.last_sign_in_at`) with live pulse dot

### 04 · Security
- Email — read-only with "Read-only" label
- Auth provider — badge with Google logo or mail icon
- Change password — enabled only when provider is `email`. Calls `supabase.auth.resetPasswordForEmail()`, shows success toast.
  Disabled + note "Managed by Google" when provider is `google`.

### 05 · Danger Zone
- Two-step delete: "Delete account" → type "delete my account" → enabled destructive button
- POST `/api/account/delete` → service role `auth.admin.deleteUser(userId)` → sign out → redirect `/login`

## Data Sources

| UI field | Source |
|---|---|
| name | `users.name` |
| email | `supabase.auth.getUser().email` |
| dnaTags | `user_profiles.profile_data.tags` |
| balance | `credits.balance` |
| total_spent (used) | `credits.total_spent` |
| welcome_credits_claimed_at | `credits.welcome_credits_claimed_at` |
| users.created_at | `users.created_at` |
| last_sign_in_at | `supabase.auth.getUser().last_sign_in_at` |
| provider | `supabase.auth.getUser().app_metadata.provider` |

## Files

| File | Purpose |
|---|---|
| `src/app/settings/page.tsx` | RSC — auth guard (redirect to /login if unauthed), renders `<AccountSettings />` |
| `src/components/settings/AccountSettings.tsx` | Client component — all sections and interactivity |
| `src/app/api/credits/redeem-promo/route.ts` | POST — validates promo, adds credits via service client |
| `src/app/api/account/delete/route.ts` | POST — deletes auth user via service client, signs out |

## Design faithfulness rules
- Use `aletheia-card` class for every section card
- Use `var(--primary)` / `#9333ea` gradient for all CTAs
- Typography: `text-[10px] font-mono uppercase tracking-[0.18em]` for eyebrow labels
- `scrollbar-primary` on any overflow containers

## Out of scope
- Avatar upload (camera button is UI-only stub)
- Notifications section (no table yet)
- Privacy / data section (no table yet)
- Top up credits (no billing integration yet)
- Re-take quiz link (no route yet)
