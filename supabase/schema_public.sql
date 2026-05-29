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
-- Core application user record.
--   • Web users:        id = auth.users.id (set by the on_auth_user_created trigger)
--   • Telegram/Tally:   id = random UUID (no auth.users counterpart)
-- (See migrations/000_merge_auth_id.sql for the history of this design.)
-- ---------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS public.users (
  id            uuid  PRIMARY KEY DEFAULT gen_random_uuid(),
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
  grounded_prompt_count integer DEFAULT 0,
  total_cost_credits    bigint DEFAULT 0,
  CONSTRAINT usage_tracking_user_model_uniq UNIQUE (user_id, model_name)
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
  total_cost_credits  bigint  DEFAULT 0,
  flushed_at          timestamptz
);


-- ---------------------------------------------------------------------------
-- chat_threads
-- Conversation envelope for the web chat UI. Today every user has one thread
-- of kind 'direct_ai'. Schema is forward-compatible with 'group' and
-- 'direct_user' kinds — they would introduce a chat_thread_members table
-- (not part of this schema yet, see specs/task_41_chat_future_extensions.md).
-- ---------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS public.chat_threads (
  id            uuid        PRIMARY KEY DEFAULT gen_random_uuid(),
  kind          text        NOT NULL CHECK (kind IN ('direct_ai', 'group', 'direct_user')),
  owner_user_id uuid        NOT NULL REFERENCES public.users(id) ON DELETE CASCADE,
  title         text,
  created_at    timestamptz NOT NULL DEFAULT now(),
  updated_at    timestamptz NOT NULL DEFAULT now()
);

-- One direct_ai thread per user. Group/DM threads are not constrained.
CREATE UNIQUE INDEX IF NOT EXISTS chat_threads_owner_direct_ai_uniq
  ON public.chat_threads (owner_user_id)
  WHERE kind = 'direct_ai';


-- ---------------------------------------------------------------------------
-- messages
-- Append-only message log. Source of truth for the user-facing web view.
-- (The `conversations` table above is the agent's rolling context window —
--  small, compacted, never user-visible. The two serve different purposes.)
--   sender_type='user'  → sender_user_id = the human's users.id, body = their text
--   sender_type='agent' → sender_user_id = NULL,                  body = agent reply
--   source              = 'web' | 'telegram' (channel that produced this row)
-- ---------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS public.messages (
  id              bigint      GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
  thread_id       uuid        NOT NULL REFERENCES public.chat_threads(id) ON DELETE CASCADE,
  sender_type     text        NOT NULL CHECK (sender_type IN ('user', 'agent')),
  sender_user_id  uuid                 REFERENCES public.users(id) ON DELETE SET NULL,
  body            text        NOT NULL,
  source          text        NOT NULL CHECK (source IN ('web', 'telegram')),
  metadata        jsonb       NOT NULL DEFAULT '{}',
  created_at      timestamptz NOT NULL DEFAULT now(),

  -- Generated tsvector for full-text search. 'simple' config = no stemming,
  -- no stopword filtering — keeps multilingual content (EN/RO/…) searchable.
  body_tsv        tsvector    GENERATED ALWAYS AS (to_tsvector('simple', body)) STORED
);

-- Newest-first pagination + cursor seeks on (thread, id).
CREATE INDEX IF NOT EXISTS messages_thread_id_idx
  ON public.messages (thread_id, id DESC);

-- Full-text search.
CREATE INDEX IF NOT EXISTS messages_body_tsv_idx
  ON public.messages USING GIN (body_tsv);


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


-- ---------------------------------------------------------------------------
-- accumulate_user_usage  (RPC — called by the Python backend)
-- Atomically increments input/output tokens, call count, grounded prompts, and cost credits.
-- ---------------------------------------------------------------------------
CREATE OR REPLACE FUNCTION public.accumulate_user_usage(
  p_user_id uuid,
  p_model_name text,
  p_input_tokens bigint,
  p_output_tokens bigint,
  p_is_grounded integer,
  p_cost_credits bigint
)
RETURNS void
LANGUAGE plpgsql
SECURITY DEFINER
AS $$
BEGIN
  INSERT INTO public.usage_tracking (
    user_id,
    model_name,
    total_input_tokens,
    total_output_tokens,
    call_count,
    grounded_prompt_count,
    total_cost_credits
  )
  VALUES (
    p_user_id,
    p_model_name,
    p_input_tokens,
    p_output_tokens,
    1,
    p_is_grounded,
    p_cost_credits
  )
  ON CONFLICT (user_id, model_name)
  DO UPDATE SET
    total_input_tokens  = public.usage_tracking.total_input_tokens + EXCLUDED.total_input_tokens,
    total_output_tokens = public.usage_tracking.total_output_tokens + EXCLUDED.total_output_tokens,
    call_count          = public.usage_tracking.call_count + 1,
    grounded_prompt_count = public.usage_tracking.grounded_prompt_count + EXCLUDED.grounded_prompt_count,
    total_cost_credits  = public.usage_tracking.total_cost_credits + EXCLUDED.total_cost_credits;
END;
$$;
