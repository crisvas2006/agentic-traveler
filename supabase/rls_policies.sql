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
-- Server-side status updates (delivered/failed/waitlisted) now run via the
-- service-role client in `frontend/src/app/actions.tsx`, which bypasses RLS.

-- Anon SELECT for COUNT only — the landing page CTA shows "{N} of 100 seats
-- taken" using a live count from the waitlist table. Anon must be able to
-- count rows but MUST NOT be able to read email addresses or other PII.
--
-- Implementation: the policy allows SELECT on the table, but the column-level
-- GRANT below restricts which columns anon may actually read. PostgREST issues
-- `SELECT id FROM waitlist` with `count=exact, head=true` for count queries,
-- which works against the column grant. `SELECT email FROM waitlist` returns
-- "permission denied for column email".
--
-- Added in DB: 2026-05-27.
CREATE POLICY "waitlist_count_anon" ON public.waitlist
  FOR SELECT
  TO anon
  USING (true);


-- ---------------------------------------------------------------------------
-- users — authenticated user may read and update their own row
-- INSERT is handled exclusively by the handle_new_auth_user trigger (SECURITY DEFINER).
-- After Task 27: users.id IS the auth UUID for web users, so the policy is a
-- direct equality check rather than a subquery.
-- ---------------------------------------------------------------------------
CREATE POLICY "users_self" ON public.users
  FOR ALL
  USING      (id = auth.uid())
  WITH CHECK (id = auth.uid());


-- ---------------------------------------------------------------------------
-- user_profiles — authenticated user may read and update their own profile
-- ---------------------------------------------------------------------------
CREATE POLICY "profiles_self" ON public.user_profiles
  FOR ALL
  USING (user_id = auth.uid());


-- ---------------------------------------------------------------------------
-- credits — authenticated user may READ their own balance (SELECT only)
-- All writes (deductions, grants, promos) go through service-role code:
--   • Python backend  → deduct_credits RPC, add_credits function
--   • Next.js Route Handler → /api/credits/welcome-grant
-- ---------------------------------------------------------------------------
CREATE POLICY "credits_self_read" ON public.credits
  FOR SELECT
  USING (user_id = auth.uid());


-- ---------------------------------------------------------------------------
-- chat_threads — authenticated user may read only their own threads.
-- All writes go through the service-role backend.
-- Forward-looking: when group/DM threads land, this will switch from a direct
-- owner check to a membership check against chat_thread_members.
-- ---------------------------------------------------------------------------
CREATE POLICY "chat_threads_self_read" ON public.chat_threads
  FOR SELECT
  USING (owner_user_id = auth.uid());


-- ---------------------------------------------------------------------------
-- messages — authenticated user may read only messages in their own threads.
-- ---------------------------------------------------------------------------
CREATE POLICY "messages_self_read" ON public.messages
  FOR SELECT
  USING (
    thread_id IN (
      SELECT id FROM public.chat_threads
      WHERE owner_user_id = auth.uid()
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

-- chat_threads + messages: read-only for authenticated users; the FastAPI
-- backend writes via the service role.
GRANT SELECT         ON public.chat_threads  TO authenticated;
GRANT SELECT         ON public.messages      TO authenticated;

-- waitlist: anon may read only id + created_at (enough for COUNT, never email).
-- The matching SELECT policy is "waitlist_count_anon" above.
GRANT SELECT (id, created_at) ON public.waitlist TO anon;


-- ---------------------------------------------------------------------------
-- link_tokens — short-lived one-time tokens for account linking or onboarding.
-- Web users insert their own token; the Python backend (service role) reads
-- and deletes it.  No web user ever needs to read another user's token.
-- ---------------------------------------------------------------------------

-- Allow a web user to insert a token for themselves.
CREATE POLICY "link_tokens_self_insert"
  ON public.link_tokens
  FOR INSERT
  TO authenticated
  WITH CHECK (user_id = auth.uid());

-- Allow a web user to read back their own pending tokens (e.g. to check status
-- or display the link again).  Not strictly required but harmless.
CREATE POLICY "link_tokens_self_select"
  ON public.link_tokens
  FOR SELECT
  TO authenticated
  USING (user_id = auth.uid());

-- Allow a web user to delete their own tokens (e.g. user cancels the flow).
CREATE POLICY "link_tokens_self_delete"
  ON public.link_tokens
  FOR DELETE
  TO authenticated
  USING (user_id = auth.uid());

-- Authenticated users need INSERT + SELECT (and optionally DELETE) on this table.
-- The backend (service role) bypasses RLS and needs no GRANT.
GRANT INSERT, SELECT, DELETE ON public.link_tokens TO authenticated;


-- ---------------------------------------------------------------------------
-- trips (Task 34)
-- Owner gets full CRUD. Service-role client bypasses RLS; app layer also
-- enforces user_id ownership (defense in depth).
-- ---------------------------------------------------------------------------
ALTER TABLE public.trips ENABLE ROW LEVEL SECURITY;

DO $$ BEGIN
  IF NOT EXISTS (SELECT 1 FROM pg_policies WHERE tablename = 'trips' AND policyname = 'trips_owner_all') THEN
    EXECUTE $p$
      CREATE POLICY trips_owner_all ON public.trips
        FOR ALL TO authenticated
        USING (user_id = auth.uid())
        WITH CHECK (user_id = auth.uid());
    $p$;
  END IF;
END $$;

GRANT SELECT, INSERT, UPDATE, DELETE ON public.trips TO authenticated;


-- ---------------------------------------------------------------------------
-- trip_destinations (Task 34)
-- Ownership derived through the parent trips row.
-- ---------------------------------------------------------------------------
ALTER TABLE public.trip_destinations ENABLE ROW LEVEL SECURITY;

DO $$ BEGIN
  IF NOT EXISTS (SELECT 1 FROM pg_policies WHERE tablename = 'trip_destinations' AND policyname = 'trip_destinations_owner_all') THEN
    EXECUTE $p$
      CREATE POLICY trip_destinations_owner_all ON public.trip_destinations
        FOR ALL TO authenticated
        USING (EXISTS (SELECT 1 FROM public.trips t WHERE t.id = trip_id AND t.user_id = auth.uid()))
        WITH CHECK (EXISTS (SELECT 1 FROM public.trips t WHERE t.id = trip_id AND t.user_id = auth.uid()));
    $p$;
  END IF;
END $$;

GRANT SELECT, INSERT, UPDATE, DELETE ON public.trip_destinations TO authenticated;


-- ---------------------------------------------------------------------------
-- trip_bookings (Task 34)
-- ---------------------------------------------------------------------------
ALTER TABLE public.trip_bookings ENABLE ROW LEVEL SECURITY;

DO $$ BEGIN
  IF NOT EXISTS (SELECT 1 FROM pg_policies WHERE tablename = 'trip_bookings' AND policyname = 'trip_bookings_owner_all') THEN
    EXECUTE $p$
      CREATE POLICY trip_bookings_owner_all ON public.trip_bookings
        FOR ALL TO authenticated
        USING (EXISTS (SELECT 1 FROM public.trips t WHERE t.id = trip_id AND t.user_id = auth.uid()))
        WITH CHECK (EXISTS (SELECT 1 FROM public.trips t WHERE t.id = trip_id AND t.user_id = auth.uid()));
    $p$;
  END IF;
END $$;

GRANT SELECT, INSERT, UPDATE, DELETE ON public.trip_bookings TO authenticated;


-- ---------------------------------------------------------------------------
-- trip_days (Task 34)
-- ---------------------------------------------------------------------------
ALTER TABLE public.trip_days ENABLE ROW LEVEL SECURITY;

DO $$ BEGIN
  IF NOT EXISTS (SELECT 1 FROM pg_policies WHERE tablename = 'trip_days' AND policyname = 'trip_days_owner_all') THEN
    EXECUTE $p$
      CREATE POLICY trip_days_owner_all ON public.trip_days
        FOR ALL TO authenticated
        USING (EXISTS (SELECT 1 FROM public.trips t WHERE t.id = trip_id AND t.user_id = auth.uid()))
        WITH CHECK (EXISTS (SELECT 1 FROM public.trips t WHERE t.id = trip_id AND t.user_id = auth.uid()));
    $p$;
  END IF;
END $$;

GRANT SELECT, INSERT, UPDATE, DELETE ON public.trip_days TO authenticated;


-- ---------------------------------------------------------------------------
-- trip_day_blocks (Task 34)
-- ---------------------------------------------------------------------------
ALTER TABLE public.trip_day_blocks ENABLE ROW LEVEL SECURITY;

DO $$ BEGIN
  IF NOT EXISTS (SELECT 1 FROM pg_policies WHERE tablename = 'trip_day_blocks' AND policyname = 'trip_day_blocks_owner_all') THEN
    EXECUTE $p$
      CREATE POLICY trip_day_blocks_owner_all ON public.trip_day_blocks
        FOR ALL TO authenticated
        USING (EXISTS (SELECT 1 FROM public.trips t WHERE t.id = trip_id AND t.user_id = auth.uid()))
        WITH CHECK (EXISTS (SELECT 1 FROM public.trips t WHERE t.id = trip_id AND t.user_id = auth.uid()));
    $p$;
  END IF;
END $$;

GRANT SELECT, INSERT, UPDATE, DELETE ON public.trip_day_blocks TO authenticated;


-- ---------------------------------------------------------------------------
-- trip_checklist (Task 34)
-- ---------------------------------------------------------------------------
ALTER TABLE public.trip_checklist ENABLE ROW LEVEL SECURITY;

DO $$ BEGIN
  IF NOT EXISTS (SELECT 1 FROM pg_policies WHERE tablename = 'trip_checklist' AND policyname = 'trip_checklist_owner_all') THEN
    EXECUTE $p$
      CREATE POLICY trip_checklist_owner_all ON public.trip_checklist
        FOR ALL TO authenticated
        USING (EXISTS (SELECT 1 FROM public.trips t WHERE t.id = trip_id AND t.user_id = auth.uid()))
        WITH CHECK (EXISTS (SELECT 1 FROM public.trips t WHERE t.id = trip_id AND t.user_id = auth.uid()));
    $p$;
  END IF;
END $$;

GRANT SELECT, INSERT, UPDATE, DELETE ON public.trip_checklist TO authenticated;

