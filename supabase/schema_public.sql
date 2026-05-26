-- =============================================================================
-- Aletheia Travel — public schema
-- Run in: Supabase → SQL Editor
-- Idempotent: safe to re-run on an existing project.
-- =============================================================================


-- ---------------------------------------------------------------------------
-- waitlist
-- Stores early-access sign-ups from the landing page.
-- ---------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS public.waitlist (
  id          uuid        PRIMARY KEY DEFAULT gen_random_uuid(),
  email       text        NOT NULL UNIQUE,
  status      text        NOT NULL DEFAULT 'pending',
  app_step    text        NOT NULL DEFAULT 'alpha_version',
  user_agent  text,
  referrer    text,
  created_at  timestamptz NOT NULL DEFAULT timezone('utc', now()),
  updated_at  timestamptz NOT NULL DEFAULT timezone('utc', now())
);


-- ---------------------------------------------------------------------------
-- users
-- Core application user record. Decoupled from auth.users on purpose:
--   • Telegram/Tally users have id = random UUID, auth_id = NULL
--   • Web users have auth_id = auth.users.id (set by the auth trigger)
-- ---------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS public.users (
  id            uuid  PRIMARY KEY DEFAULT gen_random_uuid(),
  auth_id       uuid  UNIQUE REFERENCES auth.users(id) ON DELETE CASCADE,
  telegram_id   text  UNIQUE,
  submission_id text  UNIQUE,
  name          text,
  location      text,
  source        text  DEFAULT 'tally',
  created_at    timestamptz DEFAULT now(),
  updated_at    timestamptz DEFAULT now()
);


-- ---------------------------------------------------------------------------
-- user_profiles
-- AI-generated traveler DNA: tags, 15-dimension scores, tone preference.
-- profile_data shape:
--   { tags: string[],
--     personality_dimensions_scores: { [dimension]: float },
--     tone_preference: string,
--     additional_info: string }
-- ---------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS public.user_profiles (
  user_id      uuid  PRIMARY KEY REFERENCES public.users(id) ON DELETE CASCADE,
  profile_data jsonb DEFAULT '{}',
  form_response jsonb DEFAULT '{}',
  summary      text  DEFAULT '',
  updated_at   timestamptz DEFAULT now()
);


-- ---------------------------------------------------------------------------
-- credits
-- 1 credit ≈ 1 eurocent. See backend/economy/credit_manager.py for math.
-- welcome_credits_claimed_at: NULL = not yet claimed, timestamp = claimed once.
-- ---------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS public.credits (
  user_id                    uuid    PRIMARY KEY REFERENCES public.users(id) ON DELETE CASCADE,
  balance                    integer NOT NULL DEFAULT 0,
  initial_grant              integer NOT NULL DEFAULT 0,
  total_spent                integer NOT NULL DEFAULT 0,
  used_promos                text[]  DEFAULT '{}',
  updated_at                 timestamptz DEFAULT now(),
  welcome_credits_claimed_at timestamptz DEFAULT NULL
);


-- ---------------------------------------------------------------------------
-- conversations
-- Rolling conversation window for the Telegram/web chat agent.
-- ---------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS public.conversations (
  user_id         uuid  PRIMARY KEY REFERENCES public.users(id) ON DELETE CASCADE,
  recent_messages jsonb DEFAULT '[]',
  summary         text  DEFAULT '',
  updated_at      timestamptz DEFAULT now()
);


-- ---------------------------------------------------------------------------
-- usage_tracking
-- Per-model token/call counts for cost monitoring.
-- ---------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS public.usage_tracking (
  id                    bigint GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
  user_id               uuid   REFERENCES public.users(id) ON DELETE SET NULL,
  model_name            text   NOT NULL,
  total_input_tokens    bigint DEFAULT 0,
  total_output_tokens   bigint DEFAULT 0,
  call_count            integer DEFAULT 0,
  grounded_prompt_count integer DEFAULT 0
);


-- ---------------------------------------------------------------------------
-- off_topic_state
-- Tracks off-topic violations for rate-limiting/restriction logic.
-- ---------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS public.off_topic_state (
  user_id          uuid PRIMARY KEY REFERENCES public.users(id) ON DELETE CASCADE,
  count            integer DEFAULT 0,
  last_flagged_ts  timestamptz,
  restricted_until timestamptz
);


-- ---------------------------------------------------------------------------
-- feedback
-- User-submitted feedback from the Telegram bot.
-- ---------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS public.feedback (
  id                   bigint GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
  user_id              uuid   NOT NULL REFERENCES public.users(id) ON DELETE CASCADE,
  text                 text   NOT NULL,
  category             text   NOT NULL,
  conversation_context jsonb  DEFAULT '[]',
  created_at           timestamptz DEFAULT now()
);


-- ---------------------------------------------------------------------------
-- analytics_weekly
-- Aggregated weekly metrics flushed by the backend analytics job.
-- ---------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS public.analytics_weekly (
  week_ending         date PRIMARY KEY,
  total_interactions  integer DEFAULT 0,
  new_users           integer DEFAULT 0,
  active_users        text[]  DEFAULT '{}',
  agent_calls         jsonb   DEFAULT '{}',
  token_usage         jsonb   DEFAULT '{}',
  promo_redeemed      jsonb   DEFAULT '{}',
  grounding_calls     integer DEFAULT 0,
  flushed_at          timestamptz
);


-- ---------------------------------------------------------------------------
-- deduct_credits  (RPC — called by the Python backend)
-- Atomically deducts credits, flooring at 0.
-- Returns the new balance.
-- SECURITY INVOKER: caller must have UPDATE permission (service role only,
-- since the credits RLS policy only grants SELECT to authenticated users).
-- ---------------------------------------------------------------------------
CREATE OR REPLACE FUNCTION public.deduct_credits(
  p_user_id uuid,
  p_amount  integer
)
RETURNS integer
LANGUAGE sql
AS $$
  UPDATE public.credits
  SET
    balance     = GREATEST(0, balance - p_amount),
    total_spent = total_spent + LEAST(balance, p_amount)
  WHERE user_id = p_user_id
  RETURNING balance;
$$;
