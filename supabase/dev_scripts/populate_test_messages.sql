-- =============================================================================
-- DEV ONLY — populate a specific user's direct_ai thread with N predictable
-- test messages so chat search and infinite scroll can be exercised.
--
-- Predictable naming: body = "test message <N>" for N in 1..N, where N=1 is
-- the OLDEST and N=N_MESSAGES is the NEWEST. Searching for "message2000"
-- returns the 2000th message (sender_type alternates user → agent).
--
-- Usage:
--   1. Edit `target_user_id` below to the public.users.id you want to populate.
--   2. Optionally adjust `n_messages` (default 5000).
--   3. Run in Supabase SQL Editor.
--
-- To remove the test data later: run dev_delete_test_messages.sql.
-- =============================================================================

DO $$
DECLARE
  -- ⬇️ EDIT ME ⬇️
  target_user_id uuid := '00000000-0000-0000-0000-000000000000';
  n_messages    integer := 5000;
  -- ⬆️ EDIT ME ⬆️

  v_thread_id uuid;
  v_user_exists boolean;
BEGIN
  -- Guard 1: user must exist.
  SELECT EXISTS(SELECT 1 FROM public.users WHERE id = target_user_id)
    INTO v_user_exists;
  IF NOT v_user_exists THEN
    RAISE EXCEPTION 'No public.users row for id %', target_user_id;
  END IF;

  -- Guard 2: get or create the user's direct_ai thread.
  SELECT id INTO v_thread_id
  FROM public.chat_threads
  WHERE owner_user_id = target_user_id AND kind = 'direct_ai';

  IF v_thread_id IS NULL THEN
    INSERT INTO public.chat_threads (owner_user_id, kind, title)
    VALUES (target_user_id, 'direct_ai', 'Test thread')
    RETURNING id INTO v_thread_id;
  END IF;

  -- Bulk insert. created_at is spread one minute apart so newest is "now"
  -- and oldest is `n_messages` minutes ago.
  INSERT INTO public.messages
    (thread_id, sender_type, sender_user_id, body, source, metadata, created_at)
  SELECT
    v_thread_id,
    CASE WHEN n % 2 = 1 THEN 'user' ELSE 'agent' END,
    CASE WHEN n % 2 = 1 THEN target_user_id ELSE NULL END,
    'test message ' || n,
    'web',
    jsonb_build_object('seed', true, 'n', n),
    -- oldest first: n=1 is farthest in the past
    now() - ((n_messages - n) || ' minutes')::interval
  FROM generate_series(1, n_messages) AS s(n);

  RAISE NOTICE 'Inserted % test messages into thread % for user %',
    n_messages, v_thread_id, target_user_id;
END $$;
