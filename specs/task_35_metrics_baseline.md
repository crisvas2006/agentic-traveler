# Task 35 — Metrics baseline (`analytics_events` + `metrics_daily` + six views)

> Spec lineage: `specs/proposal_trip_model_and_planning_saga.md` §7.1.5, §12.
> Ships **alongside** task 45 so every saga from task 47 onward inherits
> emission-by-default. Pre-saga: zero behaviour change. Post-saga: fleet-level
> observability without retrofit.

## 1. Problem Statement

`analytics_weekly` covers a narrow weekly aggregate (interactions, new users,
agent calls, token usage). `usage_tracking` covers per-user × per-model token
counts. Neither answers the questions the founder actually needs to operate
the product: *"How many new users this week? Where are trips getting stuck in
the planning saga? How close are we to the Supabase free-tier Realtime cap?
Which tool is failing? What does the median user cost me?"* LangSmith
(task 44) answers per-trace LLM debugging — but the LangSmith UI is not
where you look to answer fleet-level / capacity / growth questions. This
task lands the minimal data layer that does, **before** the saga model
arrives, so every saga, tool, and agent shipped in tasks 47–53 emits
metrics from birth. The design (proposal §12) is: one append-only
`analytics_events` table with a 7-day window, one `metrics_daily` rollup,
six canonical SQL views, and a third phase on the `EventEmitter`.

## 2. Goals & Non-Goals

### Goals

- The founder can answer each of these in one SQL query in the Supabase SQL
  Editor: growth funnel last 30 days, saga dropoff, data growth per user,
  errors last 24h, capacity vs free-tier limits, cost per user 30d.
- New agent code emits metric events with a single-line `events.emit("metric", {...})`
  call. The orchestrator routes those to `analytics_events` automatically.
- The `analytics_events` table never grows past ~10 MB even at 1 000 users
  — enforced by a daily `pg_cron` truncate to a 7-day window after rolling
  yesterday's events into `metrics_daily`.
- A nightly `pg_cron` job aggregates yesterday's events into
  `metrics_daily` and deletes the rolled-up events.

### Non-Goals

- A user-facing analytics page in the dashboard. Out of scope (founder
  uses Supabase SQL Editor; an admin page is a future micro-task).
- A/B testing, experimentation, segmentation.
- User-feedback collection — `feedback` table is unchanged.
- Per-trace LLM debugging — LangSmith (task 44).
- Long-term raw event storage. The 7-day window is a hard rule.
- Cross-day session reconstruction from raw events (the rollup loses
  per-event identity by design — accept this).

## 3. Acceptance Criteria

AC-1. `analytics_events` and `metrics_daily` tables exist with the schema in
  §9.1. RLS enabled on both; **no** policies → only the service role reads
  (admin-only).

AC-2. The `analytics.emit_metric(event_name, user_id, trip_id, payload)`
  Python helper inserts one row into `analytics_events` and returns within
  5 ms (asynchronously batched in production; synchronous in tests).

AC-3. A `pg_cron` job named `metrics_daily_rollup` runs at 03:00 UTC each
  day and:
  - Inserts aggregated rows for **yesterday only** into `metrics_daily`,
  - Deletes from `analytics_events` rows older than 7 days.
  Idempotent — re-running the same date does not double-count.

AC-4. The six SQL views (`vw_growth_funnel_30d`, `vw_saga_dropoff`,
  `vw_data_growth_per_user`, `vw_errors_24h`, `vw_capacity_today`,
  `vw_cost_per_user_30d`) exist and return correct results for seed data
  inserted in the integration test.

AC-5. `vw_capacity_today` returns the literal string `'WARN: approaching
  Realtime monthly cap'` when seeded with > 1 500 000 `turn_completed`
  events in the current month; otherwise `'OK'`.

AC-6. The orchestrator emits at least these four event names per turn (when
  applicable), verifiable in `analytics_events` after a chat turn:
  `turn_completed`, plus any `tool_invoked` / `error_raised` / `signup_completed`
  that the turn triggered.

AC-7. CLAUDE.md is updated with the metrics-emission convention statement
  (§12.6 from the proposal) — already partially done; this task confirms
  and tightens.

## 4. Files & Modules Touched

```
supabase/schema_public.sql                                            [modify]
supabase/rls_policies.sql                                             [modify]
backend/src/agentic_traveler/analytics/event_sink.py                  [create]
backend/src/agentic_traveler/analytics/__init__.py                    [modify]
backend/src/agentic_traveler/orchestrator/event_emitter.py            [create]
backend/src/agentic_traveler/orchestrator/agent.py                    [modify]
backend/tests/analytics/test_event_sink.py                            [create]
backend/tests/orchestrator/test_event_emitter.py                      [create — EventEmitter unit tests]
backend/tests/integration/test_metrics_views.py                       [create]
CLAUDE.md                                                             [modify — confirm convention]
README.md                                                             [modify — add ops note]
```

## 5. Constraints

- **No unbounded log table.** `analytics_events` truncates at 7 days,
  always.
- **No PII in payloads.** `user_id` is the internal users.id UUID (already
  not PII); `payload` is structured small strings (event names, tool names,
  saga names, latencies). Never a user message or chat content.
- **Batched writes.** The orchestrator buffers all `metric`-phase events
  during a turn and inserts them in one `INSERT ... VALUES (...), (...)`
  at end of turn. Never a per-event round-trip on the hot path.
- **pg_cron extension** must be enabled in the Supabase project (one-time
  manual step — see §"Manual operations").
- **Idempotent rollup.** Use `INSERT ... ON CONFLICT (day, metric,
  dimensions) DO UPDATE SET count = metrics_daily.count + EXCLUDED.count`,
  but ALSO guard with a "rolled days" tracker so re-running for the same
  date does not double-add. Simplest implementation: the rollup procedure
  records the last rolled date in a 1-row `metrics_rollup_state` table.

## 6. Edge Cases

- **emit_metric called when DB is down** → log WARN, drop the event; never
  raise (analytics must never break a user-facing turn).
- **pg_cron fails to run for one night** → the next successful run rolls
  the missed day too (the procedure iterates from last-rolled-date + 1 to
  yesterday).
- **An event payload references a deleted user/trip** → `ON DELETE SET NULL`
  on the FKs keeps the events row; the aggregate is unaffected.
- **Concurrent emit_metric calls from two turns** → both writes succeed
  independently; no shared state.
- **A new event name never seen before** → still inserted; aggregations
  group on the literal string. No enum enforcement, by design — keeps the
  emitter flexible.

## 7. Implementation Plan

### Step 1 — Tables

```sql
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
-- No policies → service role only.

CREATE TABLE IF NOT EXISTS public.metrics_daily (
  day         date    NOT NULL,
  metric      text    NOT NULL,
  dimensions  jsonb   NOT NULL DEFAULT '{}'::jsonb,
  count       bigint  NOT NULL DEFAULT 0,
  sum_value   numeric,
  PRIMARY KEY (day, metric, dimensions)
);
ALTER TABLE public.metrics_daily ENABLE ROW LEVEL SECURITY;

CREATE TABLE IF NOT EXISTS public.metrics_rollup_state (
  id              int  PRIMARY KEY DEFAULT 1 CHECK (id = 1),
  last_rolled_day date
);
INSERT INTO public.metrics_rollup_state (id, last_rolled_day)
  VALUES (1, current_date - 1) ON CONFLICT DO NOTHING;
ALTER TABLE public.metrics_rollup_state ENABLE ROW LEVEL SECURITY;
```

### Step 2 — Rollup procedure + cron

```sql
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
           coalesce(payload - 'latency_ms' - 'credits' - 'tokens', '{}'::jsonb) AS dims,
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

-- Enable extension (manual step — see Manual operations)
-- CREATE EXTENSION IF NOT EXISTS pg_cron;

-- Schedule daily at 03:00 UTC
SELECT cron.schedule(
  'metrics_daily_rollup',
  '0 3 * * *',
  $$ SELECT public.run_metrics_rollup(); $$
);
```

**Verify:** `SELECT cron.job` shows the scheduled job; run
`SELECT public.run_metrics_rollup()` once manually after seeding events to
confirm rows land in `metrics_daily`.

### Step 3 — The six views

Implement exactly the six views from proposal §12.4. (Skipping the full SQL
here for brevity — the proposal has the canonical text; copy it verbatim
into the migration. Each view must be re-creatable via
`CREATE OR REPLACE VIEW`.)

**Verify:** `SELECT * FROM vw_capacity_today` returns one row with the
expected columns.

### Step 4 — Python event sink

`backend/src/agentic_traveler/analytics/event_sink.py`:

```python
"""Batched writer to analytics_events. One INSERT per turn, never per event.

The orchestrator's EventEmitter buffers events during a turn; this module
flushes them at the end. emit_metric_now() exists for callers that need
immediate persistence (rare — e.g., signup_completed at registration time).
"""

import logging
from typing import Any
from agentic_traveler.tools.db_client import get_db

logger = logging.getLogger(__name__)


def emit_metric_now(event_name: str,
                    *,
                    user_id: str | None = None,
                    trip_id: str | None = None,
                    payload: dict[str, Any] | None = None) -> None:
    """Synchronous, single-event write. Use sparingly — prefer batched."""
    try:
        get_db().table("analytics_events").insert({
            "event_name": event_name,
            "user_id": user_id,
            "trip_id": trip_id,
            "payload": payload or {},
        }).execute()
    except Exception:
        logger.warning("emit_metric_now failed; dropping event.", exc_info=True)


def flush_metrics(rows: list[dict[str, Any]]) -> None:
    """Batched insert of accumulated events. Drops on failure (analytics
    must never break a user turn). Called by the orchestrator at end of turn."""
    if not rows:
        return
    try:
        get_db().table("analytics_events").insert(rows).execute()
    except Exception:
        logger.warning(
            "flush_metrics failed for %d rows; dropping.", len(rows), exc_info=True
        )
```

### Step 5 — EventEmitter shell

`backend/src/agentic_traveler/orchestrator/event_emitter.py`:

```python
"""EventEmitter — single sink interface, three phases (status, delta, metric).

Sagas and tools call `events.emit(phase, payload)`. The orchestrator routes
each phase to its concrete sink. Task 48 wires `status` and `delta` to SSE
and Telegram; this task wires `metric` to analytics_events.
"""

import logging
from collections import deque
from typing import Any, Callable

from agentic_traveler.analytics.event_sink import flush_metrics

logger = logging.getLogger(__name__)


class EventEmitter:
    def __init__(
        self,
        *,
        user_id: str | None,
        trip_id: str | None,
        on_status: Callable[[dict], None] | None = None,
        on_delta: Callable[[dict], None] | None = None,
    ):
        self.user_id = user_id
        self.trip_id = trip_id
        self._on_status = on_status
        self._on_delta = on_delta
        self._metric_buffer: deque[dict] = deque()

    def emit(self, phase: str, payload: dict[str, Any]) -> None:
        if phase == "status":
            if self._on_status:
                try:
                    self._on_status(payload)
                except Exception:
                    logger.warning("status sink failed.", exc_info=True)
        elif phase == "delta":
            if self._on_delta:
                try:
                    self._on_delta(payload)
                except Exception:
                    logger.warning("delta sink failed.", exc_info=True)
        elif phase == "metric":
            self._metric_buffer.append({
                "event_name": payload.get("name") or "unnamed",
                "user_id": self.user_id,
                "trip_id": self.trip_id,
                "payload": {k: v for k, v in payload.items() if k != "name"},
            })
        else:
            logger.debug("EventEmitter: unknown phase %s, dropping.", phase)

    def flush_metrics(self) -> None:
        if self._metric_buffer:
            rows = list(self._metric_buffer)
            self._metric_buffer.clear()
            flush_metrics(rows)
```

**Verify:** in a unit test, construct an `EventEmitter`, emit 3 metric
events, call `flush_metrics()`, assert the supabase client received one
`insert([3 rows]).execute()`.

### Step 6 — Wire into orchestrator

In `OrchestratorAgent._process_user_doc`, instantiate the `EventEmitter`
once per turn, pass it to dispatch (saga work in task 47 reads it), emit a
`turn_completed` metric at the end, then call `events.flush_metrics()`.
For now (pre-saga) the only emission is `turn_completed` itself plus any
`error_raised` from the existing try/except blocks.

### Step 7 — Tests

- `test_event_sink.py`: emit batched events, assert mocked supabase client
  receives one batched insert; failure path drops silently.
- `test_metrics_views.py`: insert hand-crafted seed rows into all tables
  the views read from, then query each view and assert expected output.
  Marked `integration` — runs against the real Supabase project.

## 8. Testing Plan

- **Unit:** EventEmitter routing (status/delta/metric paths each verified),
  event_sink batch insert composition, drop-on-failure behaviour.
- **Integration:** views return expected rows from seeded data; rollup
  procedure correctly aggregates and truncates; pg_cron job is registered.
- **Manual:** after deploy, paste each of the six view queries into the
  Supabase SQL Editor and verify they return data.
- **Sample expected output for `vw_capacity_today`:**

  ```
  db_size       | messages_size | events_size | messages_24h | events_mtd | realtime_status
  3072 kB       | 416 kB        | 32 kB       | 12           | 84         | OK
  ```

## 9. Conditional Sections

### 9.1 Data Model & RLS

Schema diff per Step 1. RLS enabled, no policies → service role only.
No backfill needed.

### 9.3 Observability

This *is* the observability task. Views as KPIs; rollup as the daily
heartbeat. Cloud Run logs the rollup result for ops verification.

### 9.4 Rollback Plan

- `cron.unschedule('metrics_daily_rollup')` stops the cron.
- `DROP TABLE analytics_events, metrics_daily, metrics_rollup_state CASCADE`
  removes the data layer.
- `DROP VIEW vw_*` removes the views.
- DOWN SQL committed at the bottom of the migration file but not executed
  automatically.

## 10. Findings & Follow-ups

### 10.1 Findings (noticed but not changed)

- `on_status` / `on_delta` callbacks in EventEmitter typed as `Callable[[dict], None]`
  but the existing `status_callback` in `agent.py` is `Callable[[str], None]`. Fixed in
  this task before task 48 wires live status events (see §10.2).

### 10.2 Spec deviations

- **Test file paths:** §4 originally listed `backend/tests/test_event_sink.py` and
  `backend/tests/test_metrics_views.py`. Actual paths follow existing folder conventions:
  `backend/tests/analytics/test_event_sink.py` (alongside `test_usage_tracker.py`) and
  `backend/tests/integration/test_metrics_views.py` (alongside other integration tests).

- **EventEmitter tests added:** §8 specified "EventEmitter routing (status/delta/metric
  paths each verified)" but no test file was in the original §4 list. Added
  `backend/tests/orchestrator/test_event_emitter.py` with 16 unit tests covering all
  routing paths, buffer accumulation, flush idempotency, and failure isolation.

- **Type alignment (`Callable[[dict], None]` → `Callable[[str], None]`):** `on_status`
  and `on_delta` type annotations corrected to match the existing `status_callback`
  signature; `emit("status", ...)` now passes `payload.get("message", "")` and
  `emit("delta", ...)` passes `payload.get("text", "")` to their respective callbacks.

- **`cron.schedule` idempotency fix:** the bare `SELECT cron.schedule(...)` call was not
  idempotent — re-applying the schema would create a duplicate job. Fixed with a preceding
  `SELECT cron.unschedule(jobid) FROM cron.job WHERE jobname = 'metrics_daily_rollup'`
  guard.

- **`test_usage_tracker` broken by signature change:** `_save_and_finish` gained `events`
  and `intent` parameters; the pre-existing test `test_save_and_finish_aggregates_usage_and_costs`
  was updated to pass them and patch `event_emitter.flush_metrics` so it stays unit-only.

## 11. Definition of Done

- [ ] ACs 1–7 pass.
- [ ] `ruff` clean; `pytest` unit + integration suites pass.
- [ ] pg_cron job registered; first nightly run verified after deploy.
- [ ] CLAUDE.md convention statement reaffirmed (already present from
  earlier work).
- [ ] No PII in any test fixture or seed row.

## Manual operations (user, post-implementation)

1. Enable the `pg_cron` extension in the Supabase project (Database →
   Extensions → search "pg_cron" → enable). One-time, per project.
   Free-tier compatible.
2. Apply the migration via Supabase MCP `apply_migration`.
3. After deploy: confirm `SELECT * FROM cron.job WHERE
   jobname = 'metrics_daily_rollup'` returns one row. Run
   `SELECT public.run_metrics_rollup()` manually once to seed the
   rollup pipeline.
4. After 24 hours of real traffic: query each of the six views from the
   Supabase SQL Editor. Bookmark them as Saved Queries.
