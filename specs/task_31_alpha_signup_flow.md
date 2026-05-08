# Task Spec: Alpha Access Signup Flow

## Goal
Implement a robust and automated workflow for collecting early-adopter emails for Agentic Traveler. When a user submits their email, it should be securely stored in Supabase, and they should receive a professionally designed welcome email.

**Success Criteria:**
- Email is validated on the client and server.
- Email is stored in a `alpha_signups` table in Supabase with a `pending` status.
- A "Welcome to Alpha" email is sent via Resend using a `react-email` template.
- The database record is updated to `delivered` upon successful sending.
- Errors are handled gracefully (e.g., duplicate emails, delivery failures).

---

## Approach
We will use Next.js **Server Actions** to bridge the frontend and backend. This keeps sensitive API keys (Resend, Supabase Service Role) off the client.

### 1. Data Layer (Supabase)
We will use a dedicated table `alpha_signups` to track interests.
```sql
CREATE TABLE alpha_signups (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    email TEXT UNIQUE NOT NULL,
    status TEXT DEFAULT 'pending' CHECK (status IN ('pending', 'delivered', 'failed')),
    created_at TIMESTAMPTZ DEFAULT now(),
    updated_at TIMESTAMPTZ DEFAULT now()
);
```

### 2. Email Layer (Resend + React Email)
- **React Email**: Allows us to build beautiful, responsive emails using React components.
- **Resend**: A modern developer-first email platform that integrates perfectly with React Email.

### 3. Execution Flow
1. **Frontend**: User enters email and clicks "Yes, I am in!".
2. **Action**: `requestAlphaAccess` server action is called.
3. **Database**: Insert row into `alpha_signups` with `status='pending'`.
4. **Email**: Generate HTML from the React Email template and send via Resend.
5. **Update**: On success, update status to `delivered`. On failure, update to `failed`.
6. **Response**: Return success/error message to the UI.

---

## Proposed Changes

### [NEW] `frontend/src/app/actions/signup.ts`
The core Server Action logic.

### [NEW] `frontend/src/emails/AlphaWelcomeEmail.tsx`
The email template defined using `@react-email/components`.

### [NEW] `frontend/src/lib/supabase.ts`
Supabase client initialization using service role keys.

### [MODIFY] `frontend/src/app/page.tsx`
Update `CTASection` to use the new server action and show loading/success states.

---

## Steps

1. **Setup Dependencies**
   - Install `resend`, `@react-email/components`, `@supabase/supabase-js`.
2. **Environment Configuration**
   - Add `RESEND_API_KEY` to `.env.local`.
   - Add `SUPABASE_URL` and `SUPABASE_SERVICE_ROLE_KEY` (already planned in Supabase migration spec).
3. **Database Setup**
   - Create the `alpha_signups` table in the Supabase SQL editor.
4. **Create Email Template**
   - Design a premium "Agentic Traveler" branded email using `react-email`.
5. **Implement Server Action**
   - Write the `requestAlphaAccess` function with error handling and DB updates.
6. **Connect UI**
   - Refactor `CTASection` to use `useTransition` or `useActionState` for a smooth UX.
7. **Verification**
   - Test end-to-end flow with a real email address.

---

## Risks & Open Questions
- **Resend Domain Verification**: On the free tier, Resend might only allow sending to the verified domain owner's email unless a custom domain is verified.
- **Rate Limiting**: We should implement basic rate limiting on the server action to prevent abuse.
- **Duplicate Emails**: If a user signs up twice, we should probably update their `updated_at` and re-send the email (or show a "Already signed up" message).

---

## Out of Scope
- Building a full admin dashboard to view signups.
- Implementing complex CRM integrations (e.g., Hubspot, Mailchimp).
- Handling email unsubscribes (since this is just a one-time alpha invite).
