# Task 27: Use auth.uid() directly as users.id

**Status: 🔲 COMPLETED**

> Remove the `auth_id` indirection column from `public.users`.  
> Web users' `users.id` becomes their Supabase Auth UUID (`auth.users.id`).  
> RLS on child tables simplifies from a subquery to a single equality check,  
> eliminating the PostgREST embedded-resource RLS bug class permanently.

---

## 1. Task Overview

- **Summary:** `public.users` currently uses `gen_random_uuid()` for its PK and stores the Supabase Auth UUID separately in an `auth_id` FK column. Every RLS policy on `credits`, `user_profiles`, `conversations`, etc. must subquery `users WHERE auth_id = auth.uid()` to resolve the mapping. This subquery causes PostgREST to silently return empty results for embedded resources and adds unnecessary overhead. This task merges the two IDs: for web users `users.id` becomes the Supabase Auth UUID directly.
- **Background:** Diagnosed in session 2026-05-26 — embedded `credits` join silently returned nothing because PostgREST evaluates embedded RLS subqueries in a context that conflicts with the outer query's RLS on the same table. Workaround was to query credits top-level. This task eliminates the root cause.
- **Primary Owner:** Cristian
- **Risk level:** Medium — PK migration on live tables. Safe window: before production launch with real user volume.

---

## 2. Objectives & Success Criteria

- **Goals:**
  - `public.users.id` for new web users equals `auth.users.id` (the Supabase Auth UUID).
  - `auth_id` column removed from `public.users`.
  - All RLS policies on child tables use `user_id = auth.uid()` — no subquery.
  - Telegram and Tally users (no Supabase Auth account) continue to work unchanged; their `users.id` remains a random UUID.
  - The welcome-grant Route Handler no longer needs a separate `users` lookup — it uses `user.id` from the validated JWT directly.
  - `useUserProfile` direct `credits` query works identically.
  - Embedded resource queries (e.g. `user_profiles` from `users`) work without workarounds.

- **Non-Goals:**
  - Revert the `useUserProfile` parallel-query pattern (keep it — it's more resilient regardless).
  - Modify `deduct_credits` RPC signature (it already takes `user_id uuid`; the value just changes).
  - Touch `waitlist`, `analytics_weekly` (no FK to `users`).

---

## 3. Why this is safe for Telegram/Tally users

Telegram and Tally users have `users.id = gen_random_uuid()` and `auth_id = NULL` today. After the migration their rows are untouched — `users.id` stays as the random UUID. The RLS `id = auth.uid()` evaluates to `<random uuid> = NULL` which is false, so those rows are invisible to the PostgREST API. That is correct behaviour: the Python backend always uses the service role key (bypassing RLS), so Telegram users are never affected by these policies.

---

## 4. Tables and code affected

### 4.1 Database — tables with FK to `public.users.id`

| Table | Column | Impact |
|---|---|---|
| `user_profiles` | `user_id` | PK values change for web users |
| `credits` | `user_id` | PK values change for web users |
| `conversations` | `user_id` | PK values change for web users |
| `usage_tracking` | `user_id` | values change for web users |
| `off_topic_state` | `user_id` | PK values change for web users |
| `feedback` | `user_id` | values change for web users |

### 4.2 Frontend files

| File | Change |
|---|---|
| `src/app/api/credits/welcome-grant/route.ts` | Remove `users` lookup — use `user.id` from JWT directly |
| `src/hooks/useUserProfile.ts` | No query changes needed; benefits from simplified RLS |
| `supabase/schema_public.sql` | Remove `auth_id` column, update `users` DDL |
| `supabase/auth_hooks.sql` | Update trigger to `INSERT INTO users (id, ...) VALUES (NEW.id, ...)` |
| `supabase/rls_policies.sql` | Update all policies to use `= auth.uid()` |

### 4.3 Backend (Python) — review required

Search for any code path that:
1. Looks up `public.users WHERE auth_id = $x` — after migration this becomes `WHERE id = $x`.
2. Passes `users.id` to `deduct_credits` or other RPCs by first resolving it from `auth_id`.

The Python backend uses the service role key so RLS does not break backend queries, but any explicit `auth_id` column reference in query strings must be updated.

---

## 5. Migration plan (all steps in one transaction)

### Step 1 — Pre-migration validation
```sql
-- Confirm no web user has a NULL auth_id (all web users must have an auth account)
SELECT COUNT(*) FROM public.users WHERE source = 'web' AND auth_id IS NULL;
-- Must return 0 before proceeding.

-- Confirm no auth_id collision with existing random UUIDs
-- (there shouldn't be any, but be safe)
SELECT COUNT(*) FROM public.users u1
JOIN public.users u2 ON u1.auth_id = u2.id AND u1.id <> u2.id;
-- Must return 0.
```

### Step 2 — Drop all FK constraints from child tables
```sql
ALTER TABLE public.user_profiles  DROP CONSTRAINT user_profiles_user_id_fkey;
ALTER TABLE public.credits         DROP CONSTRAINT credits_user_id_fkey;
ALTER TABLE public.conversations   DROP CONSTRAINT conversations_user_id_fkey;
ALTER TABLE public.usage_tracking  DROP CONSTRAINT usage_tracking_user_id_fkey;
ALTER TABLE public.off_topic_state DROP CONSTRAINT off_topic_state_user_id_fkey;
ALTER TABLE public.feedback        DROP CONSTRAINT feedback_user_id_fkey;
```

### Step 3 — Update child table `user_id` values for web users
```sql
-- For each child table: replace the random users.id with the auth_id value
-- Telegram/Tally rows (auth_id IS NULL) are untouched by the WHERE clause.

UPDATE public.user_profiles up
SET    user_id = u.auth_id
FROM   public.users u
WHERE  up.user_id = u.id AND u.auth_id IS NOT NULL;

UPDATE public.credits c
SET    user_id = u.auth_id
FROM   public.users u
WHERE  c.user_id = u.id AND u.auth_id IS NOT NULL;

UPDATE public.conversations cv
SET    user_id = u.auth_id
FROM   public.users u
WHERE  cv.user_id = u.id AND u.auth_id IS NOT NULL;

UPDATE public.usage_tracking ut
SET    user_id = u.auth_id
FROM   public.users u
WHERE  ut.user_id = u.id AND u.auth_id IS NOT NULL;

UPDATE public.off_topic_state ots
SET    user_id = u.auth_id
FROM   public.users u
WHERE  ots.user_id = u.id AND u.auth_id IS NOT NULL;

UPDATE public.feedback f
SET    user_id = u.auth_id
FROM   public.users u
WHERE  f.user_id = u.id AND u.auth_id IS NOT NULL;
```

### Step 4 — Update `users.id` for web users
```sql
-- Must happen after child tables are updated, before re-adding FKs.
UPDATE public.users
SET    id = auth_id
WHERE  auth_id IS NOT NULL;
```

### Step 5 — Drop `auth_id` column
```sql
ALTER TABLE public.users DROP COLUMN auth_id;
```

### Step 6 — Re-add FK constraints
```sql
ALTER TABLE public.user_profiles
  ADD CONSTRAINT user_profiles_user_id_fkey
  FOREIGN KEY (user_id) REFERENCES public.users(id) ON DELETE CASCADE;

ALTER TABLE public.credits
  ADD CONSTRAINT credits_user_id_fkey
  FOREIGN KEY (user_id) REFERENCES public.users(id) ON DELETE CASCADE;

ALTER TABLE public.conversations
  ADD CONSTRAINT conversations_user_id_fkey
  FOREIGN KEY (user_id) REFERENCES public.users(id) ON DELETE CASCADE;

ALTER TABLE public.usage_tracking
  ADD CONSTRAINT usage_tracking_user_id_fkey
  FOREIGN KEY (user_id) REFERENCES public.users(id) ON DELETE SET NULL;

ALTER TABLE public.off_topic_state
  ADD CONSTRAINT off_topic_state_user_id_fkey
  FOREIGN KEY (user_id) REFERENCES public.users(id) ON DELETE CASCADE;

ALTER TABLE public.feedback
  ADD CONSTRAINT feedback_user_id_fkey
  FOREIGN KEY (user_id) REFERENCES public.users(id) ON DELETE CASCADE;
```

### Step 7 — Update RLS policies
```sql
-- users: own row check becomes a direct equality
DROP POLICY IF EXISTS "users_self" ON public.users;
CREATE POLICY "users_self" ON public.users
  FOR ALL
  USING (id = auth.uid());

-- user_profiles: user_id IS now the auth UUID — no subquery
DROP POLICY IF EXISTS "profiles_self" ON public.user_profiles;
CREATE POLICY "profiles_self" ON public.user_profiles
  FOR ALL
  USING (user_id = auth.uid());

-- credits: same
DROP POLICY IF EXISTS "credits_self_read" ON public.credits;
CREATE POLICY "credits_self_read" ON public.credits
  FOR SELECT
  USING (user_id = auth.uid());
```

### Step 8 — Update trigger
```sql
CREATE OR REPLACE FUNCTION public.handle_new_auth_user()
RETURNS trigger
LANGUAGE plpgsql
SECURITY DEFINER
SET search_path = public
AS $$
BEGIN
  -- Use NEW.id (the auth UUID) directly as users.id — no separate random UUID.
  INSERT INTO public.users (id, name, source)
  VALUES (
    NEW.id,
    COALESCE(
      NEW.raw_user_meta_data->>'full_name',
      NEW.raw_user_meta_data->>'name',
      'Traveler'
    ),
    'web'
  );

  INSERT INTO public.user_profiles (user_id)
  VALUES (NEW.id);

  INSERT INTO public.credits (user_id, balance, initial_grant, total_spent)
  VALUES (NEW.id, 0, 0, 0);

  RETURN NEW;
END;
$$;
```

### Step 9 — Reload PostgREST schema cache
```sql
NOTIFY pgrst, 'reload schema';
```

---

## 6. Frontend changes

### `src/app/api/credits/welcome-grant/route.ts`

Remove the `users` lookup entirely. After the migration `user.id` from the JWT **is** the `users.id`.

```typescript
// BEFORE
const { data: publicUser } = await service
  .from("users").select("id").eq("auth_id", user.id).maybeSingle();
// ... then use publicUser.id

// AFTER — user.id IS the public users.id now
const { data: updated } = await service
  .from("credits")
  .update({ ... })
  .eq("user_id", user.id)   // ← direct, no lookup
  .is("welcome_credits_claimed_at", null)
  .select("balance")
  .maybeSingle();
```

This eliminates one DB round-trip from every welcome-grant call and removes the `createServiceClient` import from the lookup step (still needed for the UPDATE).

### `supabase/schema_public.sql`

Update `public.users` DDL:
- Remove `auth_id uuid UNIQUE REFERENCES auth.users(id) ON DELETE CASCADE`
- Change `id` default comment to note it equals `auth.users.id` for web users

### `supabase/auth_hooks.sql`

Replace trigger body per Step 8 above.

### `supabase/rls_policies.sql`

Replace all three policies per Step 7 above.

---

## 7. Verification queries (run after migration)

```sql
-- 1. Confirm auth_id column is gone
SELECT column_name FROM information_schema.columns
WHERE table_schema = 'public' AND table_name = 'users' AND column_name = 'auth_id';
-- Must return 0 rows.

-- 2. Confirm web user IDs now match auth UUIDs
-- (manually compare users.id with auth.users.id in the Supabase dashboard)

-- 3. Confirm all FKs are back
SELECT tc.table_name, tc.constraint_name
FROM information_schema.table_constraints tc
WHERE tc.constraint_type = 'FOREIGN KEY'
  AND tc.table_schema = 'public'
  AND tc.table_name IN ('credits','user_profiles','conversations',
                        'usage_tracking','off_topic_state','feedback');
-- Must return 6 rows.

-- 4. Confirm RLS policies updated
SELECT tablename, policyname, qual
FROM pg_policies
WHERE schemaname = 'public'
  AND tablename IN ('users','user_profiles','credits');
-- No policy qual should contain 'auth_id'.
```

---

## 8. Rollback plan

If any step fails mid-migration (e.g. FK re-add error due to orphaned rows), the state is inconsistent. Steps 2–6 should be wrapped in a single explicit transaction in the SQL editor:

```sql
BEGIN;
  -- steps 2–6 here
COMMIT;
-- If anything errors, ROLLBACK; automatically reverts everything.
```

Steps 7 and 8 (policies and trigger) are independent DDL and can be re-run idempotently.

If a post-migration bug is found and full rollback is needed: restore from Supabase's point-in-time backup (available in Project Settings → Backups). Given the current user count is < 10, a manual re-run of the inverse UPDATEs is also feasible.

---

## 9. Definition of Done

- [ ] Pre-migration validation queries return 0.
- [ ] Migration transaction commits without error.
- [ ] Verification queries all pass.
- [ ] `NOTIFY pgrst, 'reload schema'` sent.
- [ ] Welcome-grant endpoint simplified (no `users` lookup).
- [ ] `supabase/schema_public.sql`, `auth_hooks.sql`, `rls_policies.sql` updated to reflect new state.
- [ ] Sign up a new test user → profile and credits load correctly in the dashboard.
- [ ] Existing user logs in → credits show correct balance, no modal.
- [ ] Python backend reviewed for `auth_id` column references — any found are updated.
- [ ] `npx tsc --noEmit` passes with zero errors.
