-- =============================================================================
-- Aletheia Travel — auth hooks
-- Run in: Supabase → SQL Editor
-- Fires on every new Supabase Auth user sign-up (web channel only).
-- Telegram/Tally users are provisioned by the Python backend instead.
-- =============================================================================


-- ---------------------------------------------------------------------------
-- handle_new_auth_user
-- Creates three linked rows for every new auth.users entry:
--   1. public.users       — display name from OAuth/email metadata, source='web'
--   2. public.user_profiles — empty row (DNA filled by onboarding questionnaire)
--   3. public.credits       — balance=0 (welcome grant issued server-side on
--                             first dashboard login, see /api/credits/welcome-grant)
--
-- SECURITY DEFINER runs as the function owner (superuser) so it can write to
-- public.users even though the anon/authenticated roles have no INSERT policy.
-- SET search_path prevents search_path injection.
-- ---------------------------------------------------------------------------
CREATE OR REPLACE FUNCTION public.handle_new_auth_user()
RETURNS trigger
LANGUAGE plpgsql
SECURITY DEFINER
SET search_path = public
AS $$
BEGIN
  -- Use NEW.id (the auth UUID) directly as users.id — see Task 36 / migration 000.
  INSERT INTO public.users (id, name, source)
  VALUES (
    NEW.id,
    COALESCE(
      NEW.raw_user_meta_data->>'full_name',  -- Google OAuth
      NEW.raw_user_meta_data->>'name',       -- some email providers
      'Traveler'                             -- absolute last resort
    ),
    'web'
  );

  -- Empty profile row; DNA populated later via onboarding questionnaire
  INSERT INTO public.user_profiles (user_id) VALUES (NEW.id);

  -- Credits row at zero; welcome grant applied by the Next.js Route Handler
  -- on the user's first dashboard visit (one-time, server-side, configurable).
  INSERT INTO public.credits (user_id, balance, initial_grant, total_spent)
  VALUES (NEW.id, 0, 0, 0);

  RETURN NEW;
END;
$$;


-- Attach to auth.users INSERT — fires once per sign-up
CREATE TRIGGER on_auth_user_created
  AFTER INSERT ON auth.users
  FOR EACH ROW
  EXECUTE FUNCTION public.handle_new_auth_user();


-- ---------------------------------------------------------------------------
-- handle_auth_user_deleted
-- Replaces the cascade that used to come from the dropped
-- users.auth_id → auth.users(id) FK. When an auth user is deleted, remove
-- their public.users row; the existing child FKs (user_profiles, credits,
-- conversations, chat_threads, …) then cascade as before.
--
-- For Telegram/Tally users this trigger is a no-op (no public.users row
-- matches the auth UUID being deleted), so it's safe to install globally.
-- ---------------------------------------------------------------------------
CREATE OR REPLACE FUNCTION public.handle_auth_user_deleted()
RETURNS trigger
LANGUAGE plpgsql
SECURITY DEFINER
SET search_path = public
AS $$
BEGIN
  DELETE FROM public.users WHERE id = OLD.id;
  RETURN OLD;
END;
$$;

CREATE TRIGGER on_auth_user_deleted
  AFTER DELETE ON auth.users
  FOR EACH ROW
  EXECUTE FUNCTION public.handle_auth_user_deleted();
