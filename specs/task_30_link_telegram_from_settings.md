# Task 42: Link Telegram from Account Settings

**Status: ✅ COMPLETED**

> Add a "Link Telegram" button to `/settings`. Clicking it opens the
> Telegram bot with a one-time link token that the existing `/start` flow
> claims, attaching `telegram_id` to the authenticated web user's
> `public.users` row. This should work for existing Telegram-only users as well, when they create an account on the web.

---

## 1. Task Overview

- **Summary:** Web users today have `public.users` (with `id = auth.uid()`),
  but no `telegram_id`. Telegram users have `telegram_id` but historically
  no `auth_id`/web account. After Task 27 the two are unified by UUID for
  web sign-ups. We now need a one-click bridge so a web user can attach
  their Telegram chat to the same `public.users` row and seamlessly switch
  channels.

- **Background:**
  - Tally-only and Telegram-only legacy users should be able to link their
    Telegram account to their web account after creating an account on the
    web.
  - The existing onboarding flow already handles `/start <submission_id>`
    via `_handle_start` in `interfaces/routers/telegram.py`. We reuse the
    same code path with a new identifier kind.

- **Primary Owner:** Cristian

## 2. Objectives & Success Criteria

- **Goals:**
  - On `/settings`, a "Link Telegram" button. Disabled with a "Linked ✓"
    chip if `users.telegram_id` is already set.
  - Clicking the button generates a short-lived link token and opens
    `https://t.me/<BOT_USERNAME>?start=link_<token>` in a new tab.
  - The bot's `/start link_<token>` handler resolves the token to a
    `users.id`, sets `users.telegram_id = <Telegram user id>`, and replies:
    "✅ Linked! Your Telegram chat is now connected to your web account."
  - The web settings page polls (or refreshes on focus) and surfaces the
    "Linked ✓" state once it lands.
  - All historical Telegram messages for that user (`messages.source =
    'telegram'`, persisted by Task 40) immediately become visible in the
    web chat history (no migration needed — same `users.id`).

- **Non-Goals:**
  - Migrating any existing Telegram-only or Tally-only users.
  - Unlinking from `/settings` (one-direction for v1; revisit if needed).
  - Multiple Telegram accounts per user.
  - Surfacing in onboarding — settings-only entry point for v1.

- **Definition of Done:**
  - [ ] `public.web_link_tokens` table exists (or equivalent — see §3 for
        whether to use a table vs. a signed JWT-style token).
  - [ ] Web Route Handler `POST /api/account/telegram-link` returns a fresh
        token and the launch URL.
  - [ ] Telegram bot recognises `/start link_<token>`, validates the token,
        updates `users.telegram_id`, and replies success.
  - [ ] Settings page: button renders, opens Telegram, then shows "Linked ✓"
        after refresh.
  - [ ] Attempting to link a Telegram account that already belongs to
        another `users` row returns a clear error ("This Telegram account
        is already linked to a different profile").

## 3. Design choice: token storage

Two options — pick at implementation time:

- **Option A: short-lived signed token (HS256 with `LINK_TOKEN_SECRET`)**
  - Payload: `{ user_id, kind: "telegram_link", exp }`, 10-minute TTL.
  - Telegram side just verifies the signature — no DB read on the hot path.
  - Single-use enforcement requires a small `consumed_tokens` table or a
    `telegram_id` already-set check (which is naturally idempotent).
  - **Recommended** — fewer moving parts.

- **Option B: row in `public.web_link_tokens`**
  - `(token text PK, user_id uuid, expires_at timestamptz, consumed_at)`.
  - More auditable but adds a table and a write/read per link.

## 4. Components

- **Frontend**
  - `components/settings/AccountSettings.tsx` — add the button + linked-state
    chip. Use the existing `useUserProfile` data shape; extend it with
    `telegramLinked: boolean`.
  - `app/api/account/telegram-link/route.ts` — issues a token, returns
    `{ token, launchUrl }`. Validates session.

- **Backend**
  - `interfaces/routers/telegram.py` — extend `_handle_start` to recognise
    `link_<token>` payloads in addition to existing `<submission_id>`.
  - `tools/user_repo.py` — `attach_telegram_id(user_id, telegram_id)`.
  - `interfaces/dependencies.py` — token verification helper if Option A.

- **Env**
  - `LINK_TOKEN_SECRET` — random 32-byte secret, shared between Next.js
    Route Handler and Telegram router.
  - `TELEGRAM_BOT_USERNAME` — used by the Route Handler to build the
    `t.me/<bot>?start=link_<token>` URL.

## 5. Flow

```
Settings page
  └─ "Link Telegram" click
      ├─ POST /api/account/telegram-link
      │   ├─ verify Supabase session
      │   └─ returns { launchUrl: "https://t.me/MyBot?start=link_<token>" }
      └─ window.open(launchUrl)

Telegram (user is now in the bot chat)
  └─ /start link_<token>
      ├─ bot decodes the token → user_id
      ├─ if users.telegram_id already set on that row     → "Already linked."
      ├─ if telegram_id already linked to a different row → error reply
      └─ else: UPDATE users SET telegram_id = <tg> WHERE id = user_id
           → "✅ Linked! …"
```

## 6. Edge cases

- Token expired → "This link expired. Generate a new one from your
  settings."
- User already has `telegram_id` set → settings shows "Linked ✓" and the
  Route Handler returns 409 with an explanation.
- Telegram user already linked to another `users.id` → reject (the
  user_id collision is rare but possible if someone shares a token).
- Bot blocked / privacy modes → user just sees no reply; the linking
  remains pending. Should be addressed by a "Resend link" affordance.

## 7. Testing

- Unit: token issue + verify roundtrip.
- Integration: against a sandbox Telegram bot, run the full flow and
  assert `users.telegram_id` is set.
- UX: opening the link on desktop should hand off to the Telegram desktop
  client or Telegram Web; on mobile it should deeplink the app.

---

## 8. Future considerations (out of scope)

- Unlink button (resets `telegram_id` to NULL).
- One-step Tally-link from settings (analogous flow).
- Multi-channel notification preferences once another channel exists.
