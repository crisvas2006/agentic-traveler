-- =============================================================================
-- DEV ONLY — remove the seeded test messages created by
-- dev_populate_test_messages.sql for a specific user.
--
-- Identifies test rows via metadata.seed = true (set by the seeder),
-- so real Telegram/web messages for the same user are NEVER touched.
--
-- Usage:
--   1. Edit `target_user_id` below to match the user that was populated.
--   2. Run in Supabase SQL Editor.
-- =============================================================================

DO $$
DECLARE
  -- ⬇️ EDIT ME ⬇️
  target_user_id uuid := '00000000-0000-0000-0000-000000000000';
  -- ⬆️ EDIT ME ⬆️

  v_thread_id uuid;
  v_deleted   integer;
BEGIN
  SELECT id INTO v_thread_id
  FROM public.chat_threads
  WHERE owner_user_id = target_user_id AND kind = 'direct_ai';

  IF v_thread_id IS NULL THEN
    RAISE NOTICE 'No direct_ai thread for user % — nothing to delete.', target_user_id;
    RETURN;
  END IF;

  DELETE FROM public.messages
  WHERE thread_id = v_thread_id
    AND metadata ? 'seed'
    AND (metadata ->> 'seed') = 'true';
  GET DIAGNOSTICS v_deleted = ROW_COUNT;

  RAISE NOTICE 'Deleted % seeded test messages from thread %', v_deleted, v_thread_id;
END $$;
