# Task 34 — Trips data model (Option B: parent + child tables)

> Spec lineage: `specs/proposal_trip_model_and_planning_saga.md` §4, §7.1.
> Hard prerequisite for tasks 46–53. Ship this before any saga work.

## 1. Problem Statement

There is no `trips` table in Supabase today — the dashboard renders a fully
mocked Kyoto trip from `frontend/src/lib/dashboard-data.ts`, and the
backend agents have no persistent place to write trip facts they extract
from chat. The Trip Saga / Trip Builder vision in the proposal depends on
a layered, partially-filled trip document that the AI and the user mutate
across many sessions: vision summary, destinations, timeframe, country
intel snapshot, user-input bookings, day-by-day itinerary, scratchpad,
journal. This task lands the database structure that everything else
in §7 builds on. We use the **Option B** layout from §4.3 — one `trips`
parent row with JSONB columns for loose-shape sections, plus child tables
for collections that need per-item edits, ordering, or independent realtime
updates. Solo-owned (RLS = `user_id = auth.uid()`); sharing/companion model
is explicitly deferred.

## 2. Goals & Non-Goals

### Goals

- Each authenticated user can have many trips, each persisted with the full
  layered shape from §4.2 of the proposal.
- The backend has a `TripRepository` exposing CRUD with minimal LLM-friendly
  surface (`get_trip`, `upsert_trip`, `list_trip_summaries`, plus per-collection
  child upserts).
- RLS gives the trip's owner full access; nothing else.
- Realtime subscriptions on the parent `trips` row reflect changes to
  child rows transparently (via touch triggers — implemented in task 48).
- Generated TypeScript types are available for the frontend (task 51).

### Non-Goals

- The saga state machine itself — task 47.
- The frontend reading from these tables — task 51.
- Realtime triggers — task 48 (this task creates the child tables and the
  parent column they'll bump; the trigger function itself lives in task 48).
- Multi-user / companion trips — explicitly deferred per proposal §4.7.
- Attachment / document / photo storage — out of scope per the user's
  alpha cost discipline.
- Migration tooling itself — we use Supabase MCP `apply_migration` for
  this task; long-term migration policy is unchanged.

## 3. Acceptance Criteria

AC-1. The Supabase migration creates: `trips`, `trip_destinations`,
  `trip_bookings`, `trip_days`, `trip_day_blocks`, `trip_checklist` — all
  with RLS enabled and policies matching §9.1.

AC-2. An authenticated user can `INSERT` a trip via the Supabase client and
  read it back; another authenticated user querying the same row gets zero
  rows (RLS holds).

AC-3. The Python `TripRepository` exposes:
  - `get_trip(trip_id) -> Trip | None`
  - `list_trip_summaries(user_id) -> list[TripSummary]`
  - `upsert_trip(user_id, patch: dict) -> Trip`
  - `upsert_destination`, `upsert_booking`, `upsert_day_block`, `upsert_checklist_item`
  - `delete_trip(trip_id, user_id)`
  
  All use the service-key Supabase client and assert `user_id` ownership in
  the application layer (defense in depth alongside RLS).

AC-4. `saga_state` is **derived on read** — a Postgres function
  `derive_saga_state(trip_id) -> text` exists and returns one of the seven
  state names from proposal §5.3 based purely on row content (destinations,
  timeframe, dates). The `trips.saga_state` column is a cache only —
  never the source of truth (per proposal §5.3).

AC-5. `vw_trips_growth` view exists and returns one row per (week, status)
  with `count(*)`, derived from `trips.created_at` and `trips.status`.

AC-6. Generated TypeScript types in `frontend/src/lib/database.types.ts`
  include the new tables (via Supabase MCP `generate_typescript_types`).

AC-7. Backend smoke test creates a trip, upserts a destination, upserts a
  booking, upserts two day blocks, reads back via `get_trip`, asserts the
  full shape round-trips correctly.

## 4. Files & Modules Touched

```
supabase/schema_public.sql                                            [modify]
supabase/rls_policies.sql                                             [modify]
backend/src/agentic_traveler/tools/trip_repo.py                       [create]
backend/src/agentic_traveler/tools/__init__.py                        [modify]
backend/tests/tools/test_trip_repo.py                                 [create]
frontend/src/lib/database.types.ts                                    [modify]
README.md                                                             [modify]
```

## 5. Constraints

- Migration must be **idempotent** (`CREATE TABLE IF NOT EXISTS`,
  `CREATE OR REPLACE FUNCTION`, conditional `CREATE POLICY`).
- All new tables must enable RLS in the same migration. Per `CLAUDE.md` §8,
  every new table needs a policy in the same PR.
- Foreign keys to `trips` cascade DELETE; foreign keys to `users` also
  cascade DELETE on the parent. No orphan rows.
- JSONB defaults are `'{}'` or `'[]'` — never `NULL` for shape-defining
  columns (Python `dict | list` access is cleaner that way).
- `created_at` and `updated_at` `timestamptz NOT NULL DEFAULT now()` on every
  table. The parent's `updated_at` is what powers Realtime invalidation
  (task 48 wires the bump triggers).
- Do not store any file/blob in this task — no `attachments` column.
- TripRepository methods that mutate must always set `updated_at = now()`
  on the parent (until task 48 wires the auto-trigger).

## 6. Edge Cases

- **Same user creates two trips in a single transaction** → both succeed;
  ids are `gen_random_uuid()`.
- **Concurrent updates to the same trip** (web UI + agent in same second)
  → last-write-wins on the JSONB columns; child-table writes are independent
  per-row. Document; do not solve with locks.
- **User deleted** → all trips and all children cascade. No orphans.
- **Patch JSON with extra unknown fields** → accepted (`jsonb`); Python
  layer logs at DEBUG which keys it ignored. We do not strictly validate
  field whitelists in DB; saga code validates.
- **`reference_date` not set** → defaults to current date when
  `timeframe.type == "flexible"` and no `text`-derived date is present;
  app-layer fills.
- **A trip with no destinations confirmed** → `derive_saga_state` returns
  `'DREAMING'`.
- **A trip whose `start_date` is in the past and `end_date` is in the
  future** → `derive_saga_state` returns `'LIVING'`.
- **Two trips simultaneously eligible to be the active trip** (overlapping
  date ranges) → orchestrator picks the most recently `updated_at`; this
  task makes that orderable but does not enforce no-overlap.
- **A user tries to read another user's trip** via the service-key client
  → application-layer assertion in TripRepository raises
  `PermissionError`. Tested.

## 7. Implementation Plan

### Step 1 — Migration: parent table

```sql
-- File: supabase/schema_public.sql  (append; ditto for migration file)

CREATE TABLE IF NOT EXISTS public.trips (
  id              uuid        PRIMARY KEY DEFAULT gen_random_uuid(),
  user_id         uuid        NOT NULL REFERENCES public.users(id) ON DELETE CASCADE,

  -- lifecycle (mirrors metadata.status in the proposal)
  status          text        NOT NULL DEFAULT 'dreaming'
                              CHECK (status IN ('dreaming','planning','ready','active','past','archived')),
  saga_state      text,       -- cached; derive_saga_state() is canonical

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
```

**Verify:** `SELECT * FROM trips LIMIT 1` runs (returns 0 rows initially).

### Step 2 — Migration: child tables

```sql
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
```

**Verify:** all six tables visible in Supabase → Table Editor.

### Step 3 — `derive_saga_state` function

```sql
CREATE OR REPLACE FUNCTION public.derive_saga_state(p_trip_id uuid)
RETURNS text
LANGUAGE plpgsql STABLE AS $$
DECLARE
  v_status         text;
  v_start          date;
  v_end            date;
  v_today          date := current_date;
  v_confirmed_dest int;
  v_considered_dest int;
  v_pace_known     boolean;
  v_structure_known boolean;
  v_budget_known   boolean;
  v_travelers_known boolean;
  v_first_booking_exists boolean;
BEGIN
  SELECT status,
         (discovery->'timeframe'->>'start_date')::date,
         (discovery->'timeframe'->>'end_date')::date,
         (preferences ? 'pace'),
         (preferences ? 'structure'),
         (preferences ? 'budget_tier'),
         (travelers ? 'count')
    INTO v_status, v_start, v_end, v_pace_known, v_structure_known, v_budget_known, v_travelers_known
  FROM public.trips WHERE id = p_trip_id;

  IF v_status IS NULL THEN RETURN NULL; END IF;

  -- LIVING: now in [start, end]
  IF v_start IS NOT NULL AND v_end IS NOT NULL AND v_today BETWEEN v_start AND v_end THEN
    RETURN 'LIVING';
  END IF;

  -- REMEMBERING: ended within last 30d
  IF v_end IS NOT NULL AND v_today > v_end AND v_today - v_end <= 30 THEN
    RETURN 'REMEMBERING';
  END IF;

  -- READY_TO_GO: start within 7 days
  IF v_start IS NOT NULL AND v_start - v_today BETWEEN 0 AND 7 THEN
    RETURN 'READY_TO_GO';
  END IF;

  SELECT count(*) FILTER (WHERE status = 'confirmed'),
         count(*) FILTER (WHERE status = 'considering')
    INTO v_confirmed_dest, v_considered_dest
  FROM public.trip_destinations WHERE trip_id = p_trip_id;

  SELECT EXISTS (SELECT 1 FROM public.trip_bookings WHERE trip_id = p_trip_id)
    INTO v_first_booking_exists;

  -- DETAILING: bookings exist OR slot prerequisites met past ANCHORING
  IF v_first_booking_exists OR
     (v_confirmed_dest > 0 AND v_pace_known AND v_structure_known
      AND v_budget_known AND v_travelers_known) THEN
    RETURN 'DETAILING';
  END IF;

  -- ANCHORING: destination confirmed + timeframe firm
  IF v_confirmed_dest > 0 AND v_start IS NOT NULL THEN
    RETURN 'ANCHORING';
  END IF;

  -- SHAPING: destinations considered or one confirmed without firm timeframe
  IF v_considered_dest > 0 OR v_confirmed_dest > 0 THEN
    RETURN 'SHAPING';
  END IF;

  RETURN 'DREAMING';
END;
$$;
```

**Verify:** insert a row with status `'dreaming'`, no destinations →
`SELECT derive_saga_state(id)` returns `'DREAMING'`. Insert a destination
with status `'confirmed'` and `start_date = 2027-01-15` → returns
`'ANCHORING'`.

### Step 4 — RLS policies

```sql
ALTER TABLE public.trips             ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.trip_destinations ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.trip_bookings     ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.trip_days         ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.trip_day_blocks   ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.trip_checklist    ENABLE ROW LEVEL SECURITY;

CREATE POLICY trips_owner_all ON public.trips
  FOR ALL TO authenticated
  USING (user_id = auth.uid())
  WITH CHECK (user_id = auth.uid());

-- Children: ownership derived through the parent
DO $$ BEGIN
  IF NOT EXISTS (SELECT 1 FROM pg_policies WHERE policyname = 'trip_destinations_owner_all') THEN
    EXECUTE $p$
      CREATE POLICY trip_destinations_owner_all ON public.trip_destinations
        FOR ALL TO authenticated
        USING (EXISTS (SELECT 1 FROM public.trips t WHERE t.id = trip_id AND t.user_id = auth.uid()))
        WITH CHECK (EXISTS (SELECT 1 FROM public.trips t WHERE t.id = trip_id AND t.user_id = auth.uid()));
    $p$;
  END IF;
END $$;
-- Repeat the same DO block for trip_bookings, trip_days, trip_day_blocks, trip_checklist.
```

**Verify:** with a non-service `authenticated` JWT, `SELECT * FROM trips`
returns only that user's rows.

### Step 5 — Growth view

```sql
CREATE OR REPLACE VIEW public.vw_trips_growth AS
SELECT
  date_trunc('week', created_at)::date AS week,
  status,
  count(*) AS trips_created
FROM public.trips
GROUP BY 1, 2
ORDER BY 1 DESC, 2;
```

### Step 6 — Python `TripRepository`

`backend/src/agentic_traveler/tools/trip_repo.py`:

- Uses service-key `supabase` client (already in `tools/db_client.py`).
- Every method that takes a `user_id` asserts ownership via a
  `WHERE user_id = %s` clause (defense in depth — RLS would also block via
  the authenticated client, but service-key bypasses RLS so the app layer
  enforces).
- `get_trip(trip_id)` returns the full Pydantic-modeled `Trip` (parent row
  + all children loaded in parallel via 5 small queries; total < 50 ms in
  practice for trips with a few dozen rows).
- `list_trip_summaries(user_id)` returns only `{id, title, status,
  reference_date, vision_summary, updated_at}` — the *summary* shape from
  proposal §3 used to populate the LLM context without dumping the whole
  trip.
- `upsert_trip(user_id, patch)` validates the patch keys against the known
  column / JSONB-section names, applies the patch, sets `updated_at = now()`.
- `upsert_destination`, `upsert_booking`, etc. each accept a typed dict and
  insert-or-update on the natural key (id if present, else INSERT).
- A small `TripSummary` Pydantic model and a `Trip` model representing the
  loaded shape.

**Verify:** unit tests in `backend/tests/tools/test_trip_repo.py` mock the supabase client and
assert each method composes the correct query/payload.

### Step 7 — Generate TS types

After the migration:

```
# Use the Supabase MCP tool:
generate_typescript_types(project_id="dvdnrecmowamcssnwpgk")
```

Write the result to `frontend/src/lib/database.types.ts`.

**Verify:** `frontend/src/lib/database.types.ts` contains the
`trips` / `trip_*` Row / Insert / Update types.

### Step 8 — Smoke test

`backend/tests/tools/test_trip_repo.py` includes one integration test (marked
`integration`) that:
1. Creates a trip,
2. Upserts a destination, a flight booking, a day, two day blocks,
3. Reads via `get_trip`,
4. Asserts the round-tripped object matches the inputs,
5. Calls `derive_saga_state` via the RPC and asserts the expected state.

## 8. Testing Plan

- **Unit (default suite):** TripRepository query composition with a mocked
  supabase client — every method, including ownership-mismatch raising
  `PermissionError`.
- **Integration (`-m integration`):** end-to-end test from Step 8 against
  the real EU Supabase project.
- **Manual:** open the Supabase SQL Editor, run `SELECT
  derive_saga_state(...)` against three hand-crafted rows that should yield
  DREAMING / ANCHORING / LIVING.
- **Sample inputs / expected outputs:** documented in `backend/tests/tools/test_trip_repo.py`
  fixtures.

## 9. Conditional Sections

### 9.1 Data Model & RLS

Schema diff per Steps 1–5. RLS policies per Step 4. All migrations
idempotent (`IF NOT EXISTS`, conditional `CREATE POLICY` via DO block).
No backfill required (greenfield tables).

### 9.3 Observability

- TripRepository methods log at DEBUG with `user_id_hash` + method name.
  No raw trip content in logs.
- Growth view `vw_trips_growth` is the single visible KPI from this task.
  Watch the value as users create trips.

### 9.4 Rollback Plan

- The migration is additive — no existing tables modified.
- To roll back: `DROP TABLE` the six new tables in reverse-dependency
  order (children first), drop the view, drop the function. Document the
  DOWN SQL in a comment block at the bottom of the migration file but DO
  NOT execute automatically.
- **No `pg_cron` truncation job needed:** `trips` is user-owned persistent
  data (not an event/log table), so CLAUDE.md §10's "truncate after N days"
  rule does not apply. Users keep their trips indefinitely by design.

## 10. Findings & Follow-ups

### 10.1 Findings (noticed but not changed)

- No issues found beyond the deviations below.

### 10.2 Spec deviations

- **Test file path:** §4 originally listed `backend/tests/test_trip_repo.py`;
  the file was placed at `backend/tests/tools/test_trip_repo.py` (alongside
  `test_user_repo.py` and other tool-layer tests) to match the existing test
  folder convention. All references in §7, §8, and §4 updated to reflect the
  actual path.

- **No `pg_cron` truncation job:** `trips` is user-owned persistent data, not
  an event/log table, so the CLAUDE.md §10 "every unbounded table needs a
  pg_cron companion" rule does not apply. Documented in §9.4.

## 11. Definition of Done

- [ ] ACs 1–7 pass.
- [ ] §6 edge cases covered or deferred in §10.2.
- [ ] `ruff check` clean; `pytest` unit suite passes; integration suite
  passes against real Supabase.
- [ ] Generated TS types committed.
- [ ] No file outside §4 modified.
- [ ] RLS policies present and tested via JWT.
- [ ] `README.md` "Data model" section updated to reference the new tables.

## Manual operations (user, post-implementation)

1. Apply the migration via Supabase MCP (`apply_migration`) from the
   approved migration file. Do not run the SQL directly in the prod
   project's SQL Editor — keep schema in source control per
   `CLAUDE.md` §9.
2. Run `generate_typescript_types` via the Supabase MCP and commit the
   result.
3. After deploy: open the SQL Editor and confirm
   `SELECT count(*) FROM trips` returns 0, then `SELECT derive_saga_state(
   '00000000-0000-0000-0000-000000000000'::uuid)` returns NULL gracefully.
