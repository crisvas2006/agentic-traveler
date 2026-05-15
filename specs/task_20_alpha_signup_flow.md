# Task Spec: Alpha Access Signup Flow

> **Status: ✅ COMPLETED** (2026-05-14)

## Goal
Implement a robust and automated workflow for collecting early-adopter emails for Agentic Traveler. When a user submits their email, it is securely stored in Supabase, and they receive a professionally designed welcome email via Resend.

**Success Criteria:**
- ✅ Email is validated on the client and server.
- ✅ Email is stored in a `waitlist` table in Supabase with metadata (User Agent, Referrer).
- ✅ A "Welcome to Alpha" email is sent via Resend using a `react-email` template.
- ✅ The database record is updated to `delivered` upon successful sending.
- ✅ Errors are handled gracefully (e.g., duplicate emails, delivery failures).
- ✅ Client-side rate limiting (60s cooldown) implemented to prevent spam.

---

## Implementation Approach
We use **Next.js Server Actions** to securely bridge the frontend and backend. This keeps sensitive API keys (Resend, Supabase service keys) off the client.

### 1. Data Layer (Supabase)
The `waitlist` table tracks interest and delivery status.
```sql
CREATE TABLE waitlist (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    email TEXT UNIQUE NOT NULL,
    status TEXT DEFAULT 'pending' CHECK (status IN ('pending', 'delivered', 'failed')),
    app_step TEXT,
    user_agent TEXT,
    referrer TEXT,
    created_at TIMESTAMPTZ DEFAULT now(),
    updated_at TIMESTAMPTZ DEFAULT now()
);

-- Enable RLS
ALTER TABLE waitlist ENABLE ROW LEVEL SECURITY;

-- Server Actions use the Supabase Service Role (via supabase-js on server), 
-- bypassing RLS for administrative updates. 
-- Public/Anon access is restricted.
```

### 2. Email Layer (Resend + React Email)
- **React Email**: Used to build the `AlphaWelcomeEmail` component.
- **Resend**: Used via the `resend` SDK to deliver the rendered HTML.

### 3. Execution Flow
1. **Frontend**: User enters email in the `CTASection`.
2. **Action**: `signupForAlpha` server action (in `actions.tsx`) is invoked.
3. **Validation**: Server verifies the email and extracts metadata (User-Agent, Referer).
4. **Database (Insert)**: Insert row into `waitlist` with `status='pending'`.
5. **Email Delivery**: Renders `AlphaWelcomeEmail` and sends via Resend.
6. **Database (Update)**: On success, status is updated to `delivered`. On failure, it is updated to `failed`.
7. **UX**: Client-side localStorage tracks the last signup time to enforce a 60s cooldown.

---

## Technical Details

### [COMPLETED] `frontend/src/app/actions.tsx`
Contains the `signupForAlpha` Server Action. It handles:
- Supabase insertion using the server-side client.
- Resend email dispatch with error handling.
- Status rollbacks (to `failed`) on catch blocks.

### [COMPLETED] `frontend/src/emails/AlphaWelcomeEmail.tsx`
A premium, branded email template built with `@react-email/components`.

### [COMPLETED] `frontend/src/app/page.tsx`
The `CTASection` component:
- Implements `useTransition`-like behavior with manual pending states.
- Enforces a 60-second cooldown using `localStorage`.
- Provides visual feedback for success and error states.

---

## Verification Results
- ✅ **Email Delivery**: Verified that Resend successfully sends emails to the provided addresses.
- ✅ **Database Integrity**: Confirmed that `user_agent` and `referrer` fields are correctly populated.
- ✅ **Duplicate Handling**: Verified that duplicate signups trigger a resend of the welcome email but do not crash the flow.
- ✅ **Rate Limiting**: Verified that the 60s cooldown prevents rapid-fire submissions from the same browser.

---

## Risks & Open Questions
- **Domain Verification**: Currently using a verified Resend domain (`noreply@contact.XXXXXXXXXX.XXX`).
- **Bot Protection**: Client-side cooldown is a good first step, but server-side IP-based rate limiting could be added if targeted by bots.
