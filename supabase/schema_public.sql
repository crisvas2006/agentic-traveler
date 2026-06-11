-- =============================================================================
-- Aletheia Travel — public schema (reference snapshot)
--
-- This file describes the *current* state of the public schema. It is the
-- canonical reference for column shapes and RPC signatures — NOT a runnable
-- migration script. Re-running the CREATE TABLE IF NOT EXISTS blocks against
-- a database that already has the tables is a no-op and will NOT pick up
-- column additions made after the table was first created.
--
-- To change live state (add a column, rename, drop): write a separate
-- ALTER / migration statement and apply it via the Supabase dashboard or
-- migration tooling, then update this file so it continues to reflect truth.
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
  updated_at            timestamptz DEFAULT now(),
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
-- link_tokens
-- Short-lived one-time tokens that link a web account to a Telegram account.
--
-- Why not a JWT?  Telegram's ?start= deep-link parameter is hard-capped at
-- 64 bytes.  A HS256 JWT is ~160 chars — it silently gets dropped.
-- A UUID is 36 chars; with the "link_" prefix = 41 bytes. ✓
--
-- Flow:
--   1. Frontend inserts a row (user_id = auth.uid()), gets back the UUID token.
--   2. Frontend builds https://t.me/AletheiaTravelBot?start=link_<token>
--   3. User opens that link → Telegram sends /start link_<token> to the bot.
--   4. Backend looks up the token, checks expiry, links accounts, deletes row.
-- ---------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS public.link_tokens (
  token      uuid        PRIMARY KEY DEFAULT gen_random_uuid(),
  user_id    uuid        NOT NULL REFERENCES public.users(id) ON DELETE CASCADE,
  expires_at timestamptz NOT NULL DEFAULT (now() + interval '10 minutes'),
  created_at timestamptz NOT NULL DEFAULT now(),
  kind       text        NOT NULL DEFAULT 'telegram_link' CHECK (kind IN ('telegram_link', 'tally_submission'))
);

-- Auto-purge: index on expires_at so a periodic vacuum or pg_cron can clean
-- up rows cheaply; also used by the backend to spot-check expiry.
CREATE INDEX IF NOT EXISTS link_tokens_expires_at_idx
  ON public.link_tokens (expires_at);


-- ---------------------------------------------------------------------------
-- trips (Task 34)
-- Persistent trip documents. Each authenticated user can have many trips.
-- Uses Option B layout: JSONB columns for loose-shape sections + child tables
-- for collections that need per-item edits, ordering, or independent Realtime.
-- Solo-owned (RLS = user_id = auth.uid()); sharing deferred.
-- ---------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS public.trips (
  id              uuid        PRIMARY KEY DEFAULT gen_random_uuid(),
  user_id         uuid        NOT NULL REFERENCES public.users(id) ON DELETE CASCADE,

  -- lifecycle
  status          text        NOT NULL DEFAULT 'dreaming'
                              CHECK (status IN ('dreaming','planning','ready','active','past','archived')),
  saga_state      text,       -- cached; derive_saga_state() is the source of truth

  title           text,
  reference_date  date,       -- for list ordering / index
  vision_summary  text,

  -- JSONB sections (shape per proposal §4.2)
  discovery       jsonb       NOT NULL DEFAULT '{}'::jsonb,
  travelers       jsonb       NOT NULL DEFAULT '{}'::jsonb,
  preferences     jsonb       NOT NULL DEFAULT '{}'::jsonb,
  country_intel   jsonb       NOT NULL DEFAULT '[]'::jsonb,
  budget          jsonb       NOT NULL DEFAULT '{}'::jsonb,
  live_state      jsonb       NOT NULL DEFAULT '{}'::jsonb,
  scratchpad      jsonb       NOT NULL DEFAULT '{}'::jsonb,
  journal         jsonb       NOT NULL DEFAULT '{}'::jsonb,
  cover           jsonb       NOT NULL DEFAULT '{}'::jsonb,

  created_at      timestamptz NOT NULL DEFAULT now(),
  updated_at      timestamptz NOT NULL DEFAULT now()
);

CREATE INDEX IF NOT EXISTS trips_user_id_ref_date_idx
  ON public.trips (user_id, reference_date DESC);

CREATE INDEX IF NOT EXISTS trips_user_id_status_idx
  ON public.trips (user_id, status);


-- ---------------------------------------------------------------------------
-- trip_destinations (Task 34)
-- Destinations considered, confirmed, or rejected for a trip.
-- ---------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS public.trip_destinations (
  id           uuid        PRIMARY KEY DEFAULT gen_random_uuid(),
  trip_id      uuid        NOT NULL REFERENCES public.trips(id) ON DELETE CASCADE,
  name         text        NOT NULL,
  iso_country  text,
  status       text        NOT NULL DEFAULT 'considering'
                           CHECK (status IN ('considering','confirmed','rejected')),
  ord          int         NOT NULL DEFAULT 0,
  created_at   timestamptz NOT NULL DEFAULT now(),
  updated_at   timestamptz NOT NULL DEFAULT now()
);
CREATE INDEX IF NOT EXISTS trip_destinations_trip_idx
  ON public.trip_destinations (trip_id, ord);


-- ---------------------------------------------------------------------------
-- trip_bookings (Task 34)
-- User-input bookings (flights, hotels, activities, etc.).
-- No booking engine — all data is user-pasted; payload is the source of truth.
-- ---------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS public.trip_bookings (
  id                  uuid        PRIMARY KEY DEFAULT gen_random_uuid(),
  trip_id             uuid        NOT NULL REFERENCES public.trips(id) ON DELETE CASCADE,
  kind                text        NOT NULL
                                  CHECK (kind IN ('flight','accommodation','ground','restaurant','activity')),
  payload             jsonb       NOT NULL DEFAULT '{}'::jsonb,
  -- duplicated for indexing/sorting; payload is the source of truth on shape
  datetime_local      timestamp,
  confirmation_code   text,
  created_at          timestamptz NOT NULL DEFAULT now(),
  updated_at          timestamptz NOT NULL DEFAULT now()
);
CREATE INDEX IF NOT EXISTS trip_bookings_trip_kind_idx
  ON public.trip_bookings (trip_id, kind, datetime_local);


-- ---------------------------------------------------------------------------
-- trip_days (Task 34)
-- One row per itinerary day. day number (n) is 1-indexed and unique per trip.
-- ---------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS public.trip_days (
  id                 uuid        PRIMARY KEY DEFAULT gen_random_uuid(),
  trip_id            uuid        NOT NULL REFERENCES public.trips(id) ON DELETE CASCADE,
  n                  int         NOT NULL,    -- day number, 1-indexed
  date               date,
  title              text,
  energy_target      int,
  weather_snapshot   text,
  ai_note            text,
  created_at         timestamptz NOT NULL DEFAULT now(),
  updated_at         timestamptz NOT NULL DEFAULT now(),
  UNIQUE (trip_id, n)
);


-- ---------------------------------------------------------------------------
-- trip_day_blocks (Task 34)
-- Individual activity blocks within a day's itinerary.
-- ---------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS public.trip_day_blocks (
  id            uuid        PRIMARY KEY DEFAULT gen_random_uuid(),
  trip_id       uuid        NOT NULL REFERENCES public.trips(id) ON DELETE CASCADE,
  day_id        uuid        NOT NULL REFERENCES public.trip_days(id) ON DELETE CASCADE,
  ord           int         NOT NULL DEFAULT 0,
  time_slot     text        CHECK (time_slot IN ('morning','afternoon','evening','night')),
  title         text        NOT NULL,
  type          text        CHECK (type IN ('culture','wander','food','nature','rest','transit')),
  duration_min  int,
  energy        int,
  walk          text,
  why           text,
  lat           double precision,
  lng           double precision,
  created_at    timestamptz NOT NULL DEFAULT now(),
  updated_at    timestamptz NOT NULL DEFAULT now()
);
CREATE INDEX IF NOT EXISTS trip_day_blocks_day_ord_idx
  ON public.trip_day_blocks (day_id, ord);


-- ---------------------------------------------------------------------------
-- trip_checklist (Task 34)
-- Pre-trip and packing checklist items.
-- ---------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS public.trip_checklist (
  id          uuid        PRIMARY KEY DEFAULT gen_random_uuid(),
  trip_id     uuid        NOT NULL REFERENCES public.trips(id) ON DELETE CASCADE,
  scope       text        NOT NULL CHECK (scope IN ('pre_trip','packing')),
  label       text        NOT NULL,
  done        boolean     NOT NULL DEFAULT false,
  ord         int         NOT NULL DEFAULT 0,
  created_at  timestamptz NOT NULL DEFAULT now(),
  updated_at  timestamptz NOT NULL DEFAULT now()
);


-- ---------------------------------------------------------------------------
-- derive_saga_state (Task 34)
-- Derives the canonical saga state from row content; trips.saga_state is
-- only a cache. Returns one of: DREAMING | SHAPING | ANCHORING | DETAILING
--                               | READY_TO_GO | LIVING | REMEMBERING | NULL
-- ---------------------------------------------------------------------------
CREATE OR REPLACE FUNCTION public.derive_saga_state(p_trip_id uuid)
RETURNS text
LANGUAGE plpgsql STABLE AS $$
DECLARE
  v_status              text;
  v_start               date;
  v_end                 date;
  v_today               date := current_date;
  v_confirmed_dest      int;
  v_considered_dest     int;
  v_pace_known          boolean;
  v_structure_known     boolean;
  v_budget_known        boolean;
  v_travelers_known     boolean;
  v_first_booking_exists boolean;
BEGIN
  SELECT status,
         (discovery->'timeframe'->>'start_date')::date,
         (discovery->'timeframe'->>'end_date')::date,
         (preferences ? 'pace'),
         (preferences ? 'structure'),
         (preferences ? 'budget_tier'),
         (travelers ? 'count')
    INTO v_status, v_start, v_end,
         v_pace_known, v_structure_known, v_budget_known, v_travelers_known
  FROM public.trips WHERE id = p_trip_id;

  IF v_status IS NULL THEN RETURN NULL; END IF;

  -- LIVING: today is within [start, end]
  IF v_start IS NOT NULL AND v_end IS NOT NULL AND v_today BETWEEN v_start AND v_end THEN
    RETURN 'LIVING';
  END IF;

  -- REMEMBERING: ended within last 30 days
  IF v_end IS NOT NULL AND v_today > v_end AND v_today - v_end <= 30 THEN
    RETURN 'REMEMBERING';
  END IF;

  -- READY_TO_GO: departure within 7 days
  IF v_start IS NOT NULL AND v_start - v_today BETWEEN 0 AND 7 THEN
    RETURN 'READY_TO_GO';
  END IF;

  SELECT count(*) FILTER (WHERE status = 'confirmed'),
         count(*) FILTER (WHERE status = 'considering')
    INTO v_confirmed_dest, v_considered_dest
  FROM public.trip_destinations WHERE trip_id = p_trip_id;

  SELECT EXISTS (SELECT 1 FROM public.trip_bookings WHERE trip_id = p_trip_id)
    INTO v_first_booking_exists;

  -- DETAILING: bookings exist OR all planning prerequisites met
  IF v_first_booking_exists OR
     (v_confirmed_dest > 0 AND v_pace_known AND v_structure_known
      AND v_budget_known AND v_travelers_known) THEN
    RETURN 'DETAILING';
  END IF;

  -- ANCHORING: destination confirmed + start date firm
  IF v_confirmed_dest > 0 AND v_start IS NOT NULL THEN
    RETURN 'ANCHORING';
  END IF;

  -- SHAPING: at least one destination considered or confirmed
  IF v_considered_dest > 0 OR v_confirmed_dest > 0 THEN
    RETURN 'SHAPING';
  END IF;

  RETURN 'DREAMING';
END;
$$;


-- ---------------------------------------------------------------------------
-- touch_trip_updated_at (Task 37)
-- Bumps trips.updated_at whenever any child row changes, so the frontend's
-- single Realtime subscription on the parent trips row reflects child writes.
-- Complements TripRepository._touch_parent() (the Task 34 app-layer stopgap);
-- both set updated_at = now(), so they are safe to coexist.
-- Not recursive: the trigger fires only on the child tables and issues a
-- column UPDATE on trips (which has no such trigger), so it cannot re-fire.
-- ---------------------------------------------------------------------------
CREATE OR REPLACE FUNCTION public.touch_trip_updated_at() RETURNS trigger
LANGUAGE plpgsql AS $$
BEGIN
  UPDATE public.trips
     SET updated_at = now()
   WHERE id = COALESCE(NEW.trip_id, OLD.trip_id);
  RETURN COALESCE(NEW, OLD);
END;
$$;

-- Idempotent: drop + recreate one AFTER trigger per child table.
DO $$
DECLARE child_table text;
BEGIN
  FOREACH child_table IN ARRAY ARRAY[
    'trip_destinations','trip_bookings','trip_days','trip_day_blocks','trip_checklist'
  ]
  LOOP
    EXECUTE format($f$
      DROP TRIGGER IF EXISTS touch_on_%1$I ON public.%1$I;
      CREATE TRIGGER touch_on_%1$I
        AFTER INSERT OR UPDATE OR DELETE ON public.%1$I
        FOR EACH ROW EXECUTE FUNCTION public.touch_trip_updated_at();
    $f$, child_table);
  END LOOP;
END $$;


-- ---------------------------------------------------------------------------
-- vw_trips_growth (Task 34)
-- Weekly trip creation counts by status — free-tier capacity KPI.
-- ---------------------------------------------------------------------------
CREATE OR REPLACE VIEW public.vw_trips_growth AS
SELECT
  date_trunc('week', created_at)::date AS week,
  status,
  count(*) AS trips_created
FROM public.trips
GROUP BY 1, 2
ORDER BY 1 DESC, 2;


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
    total_cost_credits,
    updated_at
  )
  VALUES (
    p_user_id,
    p_model_name,
    p_input_tokens,
    p_output_tokens,
    1,
    p_is_grounded,
    p_cost_credits,
    now()
  )
  ON CONFLICT (user_id, model_name)
  DO UPDATE SET
    total_input_tokens  = public.usage_tracking.total_input_tokens + EXCLUDED.total_input_tokens,
    total_output_tokens = public.usage_tracking.total_output_tokens + EXCLUDED.total_output_tokens,
    call_count          = public.usage_tracking.call_count + 1,
    grounded_prompt_count = public.usage_tracking.grounded_prompt_count + EXCLUDED.grounded_prompt_count,
    total_cost_credits  = public.usage_tracking.total_cost_credits + EXCLUDED.total_cost_credits,
    updated_at          = now();
END;
$$;


-- ---------------------------------------------------------------------------
-- analytics_events (Task 35)
-- Append-only events log. 7-day rolling window enforced by pg_cron.
-- ---------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS public.analytics_events (
  id           bigint      GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
  occurred_at  timestamptz NOT NULL DEFAULT now(),
  event_name   text        NOT NULL,
  user_id      uuid        REFERENCES public.users(id) ON DELETE SET NULL,
  trip_id      uuid        REFERENCES public.trips(id) ON DELETE SET NULL,
  payload      jsonb       NOT NULL DEFAULT '{}'::jsonb
);
CREATE INDEX IF NOT EXISTS analytics_events_occurred_idx
  ON public.analytics_events (occurred_at DESC);
CREATE INDEX IF NOT EXISTS analytics_events_name_occurred_idx
  ON public.analytics_events (event_name, occurred_at DESC);

ALTER TABLE public.analytics_events ENABLE ROW LEVEL SECURITY;
-- No policies -> service role only


-- ---------------------------------------------------------------------------
-- metrics_daily (Task 35)
-- Aggregated daily metrics from analytics_events.
-- ---------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS public.metrics_daily (
  day         date    NOT NULL,
  metric      text    NOT NULL,
  dimensions  jsonb   NOT NULL DEFAULT '{}'::jsonb,
  count       bigint  NOT NULL DEFAULT 0,
  sum_value   numeric,
  PRIMARY KEY (day, metric, dimensions)
);
ALTER TABLE public.metrics_daily ENABLE ROW LEVEL SECURITY;
-- No policies -> service role only


-- ---------------------------------------------------------------------------
-- metrics_rollup_state (Task 35)
-- State tracker for the idempotent daily metrics rollup.
-- ---------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS public.metrics_rollup_state (
  id              int  PRIMARY KEY DEFAULT 1 CHECK (id = 1),
  last_rolled_day date
);
INSERT INTO public.metrics_rollup_state (id, last_rolled_day)
  VALUES (1, current_date - 1) ON CONFLICT DO NOTHING;
ALTER TABLE public.metrics_rollup_state ENABLE ROW LEVEL SECURITY;
-- No policies -> service role only


-- ---------------------------------------------------------------------------
-- run_metrics_rollup (Task 35)
-- Aggregates yesterday's events and deletes events older than 7 days.
-- ---------------------------------------------------------------------------
CREATE OR REPLACE FUNCTION public.run_metrics_rollup()
RETURNS void
LANGUAGE plpgsql
SECURITY DEFINER
AS $$
DECLARE
  v_last  date;
  v_to    date := current_date - 1;
  v_day   date;
BEGIN
  SELECT last_rolled_day INTO v_last FROM public.metrics_rollup_state WHERE id = 1;
  v_day := v_last + 1;
  WHILE v_day <= v_to LOOP
    INSERT INTO public.metrics_daily (day, metric, dimensions, count, sum_value)
    SELECT v_day,
           event_name,
           coalesce(payload - array['latency_ms', 'credits', 'tokens', 'scores', 'span', 'reply_len', 'purple_prose'], '{}'::jsonb) AS dims,
           count(*),
           sum((payload->>'latency_ms')::numeric)
    FROM public.analytics_events
    WHERE occurred_at::date = v_day
    GROUP BY 1, 2, 3
    ON CONFLICT (day, metric, dimensions)
      DO UPDATE SET count = metrics_daily.count + EXCLUDED.count,
                    sum_value = coalesce(metrics_daily.sum_value, 0)
                              + coalesce(EXCLUDED.sum_value, 0);
    v_day := v_day + 1;
  END LOOP;
  UPDATE public.metrics_rollup_state SET last_rolled_day = v_to WHERE id = 1;
  DELETE FROM public.analytics_events WHERE occurred_at < now() - interval '7 days';
END;
$$;

-- Schedule daily at 03:00 UTC — idempotent: unschedule first if exists.
-- NOTE: Requires pg_cron extension to be enabled in Supabase!
SELECT cron.unschedule(jobid)
  FROM cron.job
  WHERE jobname = 'metrics_daily_rollup';
SELECT cron.schedule(
  'metrics_daily_rollup',
  '0 3 * * *',
  $$ SELECT public.run_metrics_rollup(); $$
);


-- ---------------------------------------------------------------------------
-- Canonical SQL views for Metrics (Task 35)
-- ---------------------------------------------------------------------------

-- 12.4.1  Growth funnel — last 30 days
CREATE OR REPLACE VIEW public.vw_growth_funnel_30d AS
SELECT
  count(*) FILTER (WHERE u.created_at >= now() - interval '30 days')
    AS signups,
  count(DISTINCT m.sender_user_id) FILTER (
    WHERE m.created_at >= now() - interval '30 days'
      AND m.sender_type = 'user') AS first_message_senders,
  count(DISTINCT t.user_id) FILTER (
    WHERE t.created_at >= now() - interval '30 days') AS first_trip_creators,
  count(DISTINCT t.user_id) FILTER (
    WHERE t.status = 'active'
      AND t.updated_at >= now() - interval '30 days') AS first_trip_actives
FROM public.users u
LEFT JOIN public.messages m ON m.sender_user_id = u.id
LEFT JOIN public.trips    t ON t.user_id        = u.id;

-- 12.4.2  Saga dropoff — where trips are stalled
CREATE OR REPLACE VIEW public.vw_saga_dropoff AS
SELECT saga_state, status, count(*) AS trips,
       max(updated_at) AS most_recent_activity
FROM public.trips
WHERE updated_at < now() - interval '14 days'
  AND status NOT IN ('active', 'past', 'archived')
GROUP BY saga_state, status
ORDER BY trips DESC;

-- 12.4.3  Data growth per user — feeds capacity forecasting
CREATE OR REPLACE VIEW public.vw_data_growth_per_user AS
SELECT
  u.id AS user_id,
  u.created_at,
  count(DISTINCT t.id)  AS trips,
  count(DISTINCT m.id)  AS messages,
  count(DISTINCT b.id)  AS bookings,
  count(DISTINCT db.id) AS day_blocks
FROM public.users u
LEFT JOIN public.trips           t  ON t.user_id        = u.id
LEFT JOIN public.messages        m  ON m.sender_user_id = u.id
LEFT JOIN public.trip_bookings   b  ON b.trip_id        = t.id
LEFT JOIN public.trip_day_blocks db ON db.trip_id       = t.id
GROUP BY u.id, u.created_at;

-- 12.4.4  Error rate by saga / tool — last 24 h
CREATE OR REPLACE VIEW public.vw_errors_24h AS
SELECT
  payload->>'scope'       AS scope,
  payload->>'error_class' AS error_class,
  count(*)                AS errors
FROM public.analytics_events
WHERE event_name = 'error_raised'
  AND occurred_at >= now() - interval '24 hours'
GROUP BY 1, 2
ORDER BY errors DESC;

-- 12.4.5  Capacity vs Supabase free-tier limits
CREATE OR REPLACE VIEW public.vw_capacity_today AS
SELECT
  pg_size_pretty(pg_database_size(current_database()))      AS db_size,
  pg_size_pretty(pg_total_relation_size('public.messages')) AS messages_size,
  pg_size_pretty(pg_total_relation_size('public.analytics_events'))
                                                            AS events_size,
  (SELECT count(*) FROM public.messages
     WHERE created_at >= now() - interval '24 hours')       AS messages_24h,
  (SELECT count(*) FROM public.analytics_events
     WHERE occurred_at >= date_trunc('month', now()))       AS events_mtd,
  -- Realtime monthly events ≈ turn_completed × ~1 subscriber per active session.
  -- Free-tier cap = 2 000 000 / month. Warn at 75%.
  CASE
    WHEN (SELECT count(*) FROM public.analytics_events
            WHERE event_name = 'turn_completed'
              AND occurred_at >= date_trunc('month', now())) > 1500000
    THEN 'WARN: approaching Realtime monthly cap'
    ELSE 'OK'
  END AS realtime_status;

-- 12.4.6  Cost per active user — last 30 days
CREATE OR REPLACE VIEW public.vw_cost_per_user_30d AS
SELECT
  u.id, u.created_at,
  coalesce(sum(ut.total_cost_credits), 0) AS cost_credits_30d,
  count(DISTINCT t.id)                    AS trips
FROM public.users u
LEFT JOIN public.usage_tracking ut ON ut.user_id = u.id
LEFT JOIN public.trips          t  ON t.user_id  = u.id
WHERE u.created_at >= now() - interval '30 days'
GROUP BY u.id, u.created_at
ORDER BY cost_credits_30d DESC;
