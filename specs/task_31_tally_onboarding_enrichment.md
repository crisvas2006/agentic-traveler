# Task 31: Tally Onboarding Enrichment and Account Linking Webhook

**Status: ✅ COMPLETED**

> Enhance the Telegram, Web Chat, and Tally onboarding systems to seamlessly handle personalized onboarding forms for linked users. Instead of blocking users if they haven't filled out the onboarding questionnaire, allow them to chat immediately once linked, but invite them to complete the form using a secure, single-use personalized onboarding link containing a long-lived `idToken` that maps to their existing profile and merges webhook responses gracefully. Update the token table name to `link_tokens` globally and ensure no DB user IDs are ever exposed.

---

## 1. Task Overview

- **Summary:** Currently, the Telegram bot has loose and confusing code around `/start` where it checks for `submission_id` and blocks the user if it's missing, which is unreachable for unlinked users and confusing for linked users. We want to revise this: do not block users who haven't completed the Tally form, but if they link their Telegram account to their web account for the first time via the `link_token` flow, and their profile shows they have not yet completed the onboarding form, we will generate a secure, 7-day token and invite them to complete it using a personalized link: `https://tally.so/r/formID?idToken=<token>`. We will also display this thoughtful recommendation to web chat users in their first active conversation if they haven't completed the form. When Tally sends a webhook submission with that `idToken`, we resolve their existing web user record, update it with their submission details, and save their traveler profile responses.

- **Background:**
  - We are renaming the `telegram_link_tokens` table to `link_tokens` and adding a `kind` column to support two kinds of tokens:
    1. `'telegram_link'` (10-minute TTL, default)
    2. `'tally_submission'` (7-day TTL, used to link Tally submissions to existing profiles)
  - The Tally form hidden field has the format:
    ```json
    {
      "key": "question_dPyN4N_fd3acc06-ff4d-4427-836a-64609a7985af",
      "label": "idToken",
      "type": "HIDDEN_FIELDS",
      "value": "token_value_here"
    }
    ```
    We must ensure the webhook handles this mapping robustly and tests cover this.

- **Primary Owner:** Cristian

---

## 2. Objectives & Success Criteria

- **Goals:**
  - Rename the table `telegram_link_tokens` to `link_tokens` across the database schema, RLS policies, backend, frontend API, and mock tests.
  - Add a `kind` column to `public.link_tokens` to support both `'telegram_link'` and `'tally_submission'` kinds.
  - In `_handle_telegram_link`, check if the user's `user_profiles.form_response` is empty or missing. If empty, generate a 7-day `'tally_submission'` token and append a personalized onboarding invitation link `https://tally.so/r/formID?idToken=<token>` to the successful linkage message.
  - In `chat.py` (web chat router), apply the same check when the user sends a message. If they haven't completed the form, append the thoughtful onboarding recommendation to the agent response with the 7-day personalized onboarding link.
  - Format the recommendation thoughtfully to feel useful rather than mandatory, mentioning that the link is valid for 7 days and can always be generated again in website settings.
  - In `_handle_start`, remove the unreachable and restrictive check for missing `submission_id` that told users to complete the form. For already linked users sending plain `/start`, reply with a warm welcome and allow them to continue chatting.
  - In `tally_webhook`, extract `idToken` (supporting `f.get("label") == "idToken"` or key `"question_dPyN4N_fd3acc06-ff4d-4427-836a-64609a7985af"`).
  - If a valid `idToken` is present, resolve the existing web `user_id` from the database, update their record (`submission_id`, `name`, `location`), delete the single-use token, and save their form responses.
  - Ensure we do NOT notify the user on Telegram that their traveler DNA is synced, but still trigger the background profiling (`ProfileAgent`).
  - Write complete unit/integration tests covering the database alteration, invitation message, Tally webhook merging, and background profiling.
  - Update `README.md` to document the new personalized onboarding flow.

- **Non-Goals:**
  - Refactoring other unlinked user routing or guards.
  - Modifying any of the frontend components beyond table references in the API route.

- **Definition of Done:**
  - [ ] Schema updated in `schema_public.sql` to rename table to `link_tokens` and include `kind`.
  - [ ] RLS policies updated in `rls_policies.sql` to reference `link_tokens`.
  - [ ] DB migration successfully run to execute the rename and column additions.
  - [ ] Frontend route updated to use `link_tokens`.
  - [ ] Telegram `_handle_telegram_link` generates and sends personalized Tally link if profile is incomplete.
  - [ ] Web chat sends the same thoughtful invitation if profile is incomplete.
  - [ ] Unreachable block in `_handle_start` deleted; plain `/start` handles already linked users gracefully.
  - [ ] Tally webhook handles `idToken`, associates it with existing web user, performs an update (not upsert), deletes token.
  - [ ] Root `README.md` updated.
  - [ ] Standard pytest suite runs and all tests pass (including new mock tests covering the new flows).

---

## 3. Database Schema Revisions

We rename and revise `public.telegram_link_tokens` to `public.link_tokens`:

```sql
-- Rename the table
ALTER TABLE IF EXISTS public.telegram_link_tokens RENAME TO link_tokens;

-- Rename constraints and index if needed
ALTER INDEX IF EXISTS public.telegram_link_tokens_pkey RENAME TO link_tokens_pkey;
ALTER INDEX IF EXISTS public.telegram_link_tokens_expires_at_idx RENAME TO link_tokens_expires_at_idx;

-- Add kind column if not exists
ALTER TABLE public.link_tokens 
  ADD COLUMN IF NOT EXISTS kind text NOT NULL DEFAULT 'telegram_link' CHECK (kind IN ('telegram_link', 'tally_submission'));
```

Updating `supabase/schema_public.sql` definition:
```sql
CREATE TABLE IF NOT EXISTS public.link_tokens (
  token      uuid        PRIMARY KEY DEFAULT gen_random_uuid(),
  user_id    uuid        NOT NULL REFERENCES public.users(id) ON DELETE CASCADE,
  expires_at timestamptz NOT NULL DEFAULT (now() + interval '10 minutes'),
  created_at timestamptz NOT NULL DEFAULT now(),
  kind       text        NOT NULL DEFAULT 'telegram_link' CHECK (kind IN ('telegram_link', 'tally_submission'))
);

CREATE INDEX IF NOT EXISTS link_tokens_expires_at_idx
  ON public.link_tokens (expires_at);
```

---

## 4. Webhook and Link Verification Logic

### 1. Account Link Invitation Flow (`telegram.py` -> `_handle_telegram_link`)
```python
# Check if profile form_response is filled out
profile_res = db.table("user_profiles").select("form_response").eq("user_id", web_user_id).maybe_single().execute()
has_completed_form = False
if profile_res and profile_res.data:
    form_resp = profile_res.data.get("form_response")
    if form_resp and isinstance(form_resp, dict) and len(form_resp) > 0:
        has_completed_form = True

if not has_completed_form:
    from datetime import datetime, timezone, timedelta
    # Generate 7-day tally_submission token
    expires_at = datetime.now(timezone.utc) + timedelta(days=7)
    tally_token_res = db.table("link_tokens").insert({
        "user_id": web_user_id,
        "kind": "tally_submission",
        "expires_at": expires_at.isoformat()
    }).execute()
    
    if tally_token_res and tally_token_res.data:
        id_token = tally_token_res.data[0]["token"]
        onboarding_url = f"https://tally.so/r/formID?idToken={id_token}"
        
        # Append invitation message to Telegram response
        send_telegram_message(
            chat_id,
            "💡 *A Thoughtful Recommendation for Your Travels*\n\n"
            "To help me provide highly personalized recommendations tailored to your traveler style, "
            "you might enjoy taking 3 minutes to fill out our onboarding questionnaire! It maps out your unique Traveler DNA.\n\n"
            "Here is your personalized link (valid for 7 days, and you can always generate a new one in website settings):\n"
            f"{onboarding_url}"
        )
```

### 2. Tally Webhook Matching Flow (`tally.py` -> `tally_webhook`)
```python
    id_token = user_fields.pop("idToken", None)
    web_user_id = None
    if id_token:
        # Check if exists and not expired
        token_res = db.table("link_tokens").select("user_id, expires_at").eq("token", id_token).eq("kind", "tally_submission").maybe_single().execute()
        if token_res and token_res.data:
            from datetime import datetime, timezone
            expires_raw = token_res.data["expires_at"]
            if expires_raw.endswith("Z"):
                expires_raw = expires_raw[:-1] + "+00:00"
            expires_at = datetime.fromisoformat(expires_raw)
            if expires_at >= datetime.now(timezone.utc):
                web_user_id = token_res.data["user_id"]
            db.table("link_tokens").delete().eq("token", id_token).execute()

    if web_user_id:
        # Update existing user instead of upsert
        db.table("users").update({
            "submission_id": response_id,
            "name": name,
            "location": location,
        }).eq("id", web_user_id).execute()
        user_id = web_user_id
    else:
        # Fallback to default legacy upsert behavior
        ...
```

---

## 5. Testing & Validation

### Acceptance Scenarios
1. **Unregistered user plain `/start` block**: Unregistered user gets blocked at the webhook layer with a signup redirect (already existing).
2. **Linked user plain `/start`**: User who is already registered/linked sends a plain `/start` command -> Greeted with a friendly welcome message, NOT blocked.
3. **Linked user without Form Response links account**:
   - Goes through `/start link_<token>`.
   - Accounts are successfully linked.
   - Profile check detects incomplete form response.
   - System inserts a `'tally_submission'` token.
   - User gets a warm "Linked" greeting + a thoughtful, useful onboarding invitation link.
4. **Web Chat Onboarding Invitation**:
   - User has not completed form.
   - User sends a message in web chat.
   - System checks if active token exists, generates a 7-day token if not, and appends the recommendation text at the bottom of the reply.
5. **Tally ingestion with `idToken`**:
   - Webhook receives payload with `idToken`.
   - Resolves token to the existing `web_user_id`.
   - Updates `users` (attaching `submission_id`) and saves profile.
   - Deletes single-use token.
   - Triggers background DNA generation but does NOT alert Telegram user.
