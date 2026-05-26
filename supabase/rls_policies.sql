-- =============================================================================
-- Aletheia Travel — Row-Level Security policies
-- Run in: Supabase → SQL Editor
-- All tables have RLS ENABLED (auto-applied by the rls_auto_enable event trigger).
-- These policies define what authenticated web users may read/write.
-- The Python backend uses the SERVICE ROLE KEY and bypasses RLS entirely.
-- =============================================================================


-- ---------------------------------------------------------------------------
-- waitlist — public write (landing page), no authenticated read needed
-- ---------------------------------------------------------------------------
CREATE POLICY "Allow anonymous inserts" ON public.waitlist
  FOR INSERT TO anon
  WITH CHECK (true);

-- NOTE: The "Allow anonymous updates" policy that previously existed here has been
-- intentionally dropped. Anonymous UPDATE on waitlist is unnecessary and was a
-- security risk (unauthenticated actors could overwrite any waitlist row).
-- Dropped in DB: 2026-05-25. Do NOT re-add.


-- ---------------------------------------------------------------------------
-- users — authenticated user may read and update their own row
-- INSERT is handled exclusively by the handle_new_auth_user trigger (SECURITY DEFINER).
-- ---------------------------------------------------------------------------
CREATE POLICY "users_self" ON public.users
  FOR ALL
  USING      (auth_id = auth.uid())
  WITH CHECK (auth_id = auth.uid());
-- USING:      filters which rows the user can touch (checked against the OLD row).
-- WITH CHECK: validates the resulting row after INSERT/UPDATE so a user cannot
--             change their own auth_id to steal another user's row.


-- ---------------------------------------------------------------------------
-- user_profiles — authenticated user may read and update their own profile
-- ---------------------------------------------------------------------------
CREATE POLICY "profiles_self" ON public.user_profiles
  FOR ALL
  USING (
    user_id IN (
      SELECT id FROM public.users WHERE auth_id = auth.uid()
    )
  );


-- ---------------------------------------------------------------------------
-- credits — authenticated user may READ their own balance (SELECT only)
-- All writes (deductions, grants, promos) go through service-role code:
--   • Python backend  → deduct_credits RPC, add_credits function
--   • Next.js Route Handler → /api/credits/welcome-grant
-- ---------------------------------------------------------------------------
CREATE POLICY "credits_self_read" ON public.credits
  FOR SELECT
  USING (
    user_id IN (
      SELECT id FROM public.users WHERE auth_id = auth.uid()
    )
  );


-- =============================================================================
-- GRANT statements — must be run AFTER table creation
-- Context: tables created via SQL editor do NOT automatically inherit the
-- default privileges that the Supabase dashboard would normally configure.
-- Without these grants the PostgREST layer returns 403 for authenticated users
-- even when RLS policies allow the operation.
-- Run in: Supabase → SQL Editor
-- =============================================================================

-- users: read own row (for profile display) and update own row (future settings page)
GRANT SELECT, UPDATE ON public.users         TO authenticated;

-- user_profiles: read and update own profile (DNA tags, preferences)
GRANT SELECT, UPDATE ON public.user_profiles TO authenticated;

-- credits: read-only for authenticated users; writes go through service-role only
GRANT SELECT         ON public.credits       TO authenticated;
