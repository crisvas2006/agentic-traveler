# Task 41 — Live mood check-in saga + Journal saga (post-trip)

> Spec lineage: `specs/proposal_trip_model_and_planning_saga.md` §5.4 (MoodCheckin, Journal).
> Depends on tasks 34–40.

## 1. Problem Statement

Two sagas wrap the lifecycle endpoints of a trip. The **MoodCheckinSaga**
fires daily during `LIVING` if no mood has been logged today — a soft
prompt, never insistent, that captures the user's current energy / state
into `trips.live_state.last_mood`. The TripAgent uses this signal to
adjust today's itinerary (swap to indoor activities if "tired and raining",
suggest a lighter evening if "low energy"). The **JournalSaga** activates
in `REMEMBERING` (the first 30 days post-trip) and lightly captures
highlights, regrets, and tags-learned into `trips.journal` — material
that seeds future trip recommendations and a possible blog. Both are
small sagas; together they close the lifecycle loop.

## 2. Goals & Non-Goals

### Goals

- During a LIVING trip, the bot sends a single mood-check prompt per
  day, only if the user has not already self-reported.
- The mood signal influences the TripAgent's swap suggestions for that
  day.
- During REMEMBERING, the bot offers one journal prompt per session
  (not per turn). User can ignore.
- All captured data is structured and persistable; nothing is lost to
  free text.

### Non-Goals

- Photo upload — text-only journaling.
- Push notifications — no, this is a conversational nudge only.
- Long-term blog publishing — task 42 handles content seeding.
- Trip-recap email — out of scope (could be a future micro-task).

## 3. Acceptance Criteria

AC-1. `MoodCheckinSaga.should_activate` returns owner=true only when:
  - `trip.status == 'active'`,
  - the current Python-local day matches `trip.live_state.current_day_n`
    or is computable from `trip.start_date`,
  - no `live_state.last_mood.logged_at` exists for today's date.

AC-2. The mood prompt is one sentence ≤ 100 chars, varied across calls
  from a fixed library of 8 phrasings (random with same-day stability).

AC-3. When the user replies with a mood-shaped message, the saga parses
  it (gemini-3.1-flash-lite) into `{label: str, energy: 1-5}` and writes
  to `trips.live_state.last_mood`.

AC-4. The TripAgent reads `live_state.last_mood` in its profile_summary
  (already wired by task 36) — its swap suggestions adjust accordingly.

AC-5. `JournalSaga.should_activate` returns owner=true only when:
  - `derive_saga_state == 'REMEMBERING'`,
  - the user message mentions the past trip (the trip resolver picked it),
  - it has not asked a journal prompt in this conversation thread today.

AC-6. The journal prompt is one of: "What stuck with you?", "What
  surprised you?", "What would you do differently?" — randomized but
  conversation-stable.

AC-7. The user's free-text journal reply is structured into
  `journal.entries[]` (text + day_n if mentioned) and `journal.highlights[]`
  / `journal.regrets[]` if the user used clear phrasing.

AC-8. Both sagas emit metrics: `mood_logged`, `mood_check_skipped`,
  `journal_prompt_offered`, `journal_entry_captured`.

## 4. Files & Modules Touched

```
backend/src/agentic_traveler/orchestrator/sagas/mood_checkin.py      [create]
backend/src/agentic_traveler/orchestrator/sagas/journal.py           [create]
backend/src/agentic_traveler/orchestrator/sagas/dispatcher.py        [modify]
backend/src/agentic_traveler/tools/trip_repo.py                      [modify]
backend/src/agentic_traveler/orchestrator/profile_utils.py           [modify — last 3 moods in LIVING]
backend/tests/test_mood_saga.py                                      [create]
backend/tests/test_journal_saga.py                                   [create]
frontend/src/components/dashboard/LiveStateCard.tsx                  [from task 40 — wire mood widget]
frontend/src/components/dashboard/JournalSection.tsx                 [from task 40 — wire entry edit]
README.md                                                            [modify]
```

## 5. Constraints

- The MoodCheckinSaga **must not** interrupt the user mid-turn. If the
  user asks a question, the saga answers the question; the mood prompt
  is deferred to the start of the next user message.
- The JournalSaga **never** interrogates — at most one prompt per
  session, then silent unless re-triggered.
- All saga prompts use the cheapest model (`gemini-3.1-flash-lite`)
  because they're tiny.
- No new tables; both sagas write into existing JSONB sections of `trips`.

## 6. Edge Cases

- **User logs mood twice in a day** → second log overwrites first;
  no error.
- **Trip ends mid-day** → MoodCheckinSaga deactivates as soon as
  `derive_saga_state` flips to REMEMBERING.
- **REMEMBERING window expires (30 days post-trip)** → JournalSaga
  deactivates; the trip is archived.
- **Journal reply is one word ("good")** → captured verbatim as an
  entry; no structure extracted.
- **User skips the mood prompt with another question** → MoodCheckinSaga
  yields owner role; logs a `mood_check_skipped` metric.

## 7. Implementation Plan

### Step 1 — MoodCheckinSaga

```python
_PROMPTS = [
    "How's the day feeling so far?",
    "Where's your energy at?",
    "What's the mood today?",
    "Quick check: how are you holding up?",
    "How are you arriving into today?",
    "Feeling steady or off?",
    "Energy check — full bars or low?",
    "What kind of day is it shaping up to be?",
]

class MoodCheckinSaga(BaseSaga):
    name = "MoodCheckinSaga"

    def should_activate(self, intent, entities, trip, state):
        if not trip or trip.get("status") != "active":
            return False, False
        if entities.get("mood"):
            return True, False   # listener — capture & write
        last = ((trip.get("live_state") or {}).get("last_mood") or {}).get("logged_at")
        if _is_today(last):
            return False, False
        return True, False   # listener: it'll add a status-event tag

    @traceable(name="saga.mood_checkin.run")
    def run(self, message, user_doc, trip, state, conv, events):
        if (entities := state.get("entities") or {}).get("mood"):
            parsed = _parse_mood(message)
            return SagaResult(
                side_effects=[SideEffect("trip_patch", {
                    "trip_id": trip["id"],
                    "patch": {"live_state.last_mood": {**parsed, "logged_at": utcnow_iso()}}
                })],
                state_delta={"mood_logged_today": True},
            )
        # Inject a status hint so the owner saga can mention it,
        # but never override the owner's reply.
        events.emit("status", {"phase": "mood_hint",
                               "text": _pick_prompt(trip["id"])})
        return SagaResult()
```

### Step 2 — JournalSaga

```python
class JournalSaga(BaseSaga):
    name = "JournalSaga"

    def should_activate(self, intent, entities, trip, state):
        if not trip:
            return False, False
        if derive_saga_state_local(trip) != "REMEMBERING":
            return False, False
        if state.get("journal_prompted_today"):
            return False, False
        return True, True
```

The saga's `run` either asks the prompt or captures the user's reply
into `journal.entries[]` with light structure extraction (highlights /
regrets) via flash-lite.

### Step 3 — Frontend wiring (LiveStateCard + JournalSection)

`LiveStateCard.tsx`:
- Mood emoji slider (😩 → 🙂 → 😀) translates to `energy: 1-5`.
- Optional one-line text input for `label`.
- Save → server action → updates `trip.live_state.last_mood` directly.

`JournalSection.tsx`:
- One textarea per day (lazy-loaded).
- "What stuck with you?" / "Regrets?" inputs.

### Step 4 — Tests

`test_mood_saga.py`: activation rules; double-log; today-already-logged.
`test_journal_saga.py`: 30-day window; one prompt per session.

## 8. Testing Plan

- **Unit:** activation rules; mood parsing; journal entry extraction.
- **Integration:** during a fake LIVING trip, run two turns — first
  turn: bot greets + mood prompt; second turn: user logs mood, bot
  responds to current question; verify `live_state.last_mood` written.
- **Manual:** Telegram + web: confirm mood prompt frequency feels right
  (once per day, not nagging).

## 9. Conditional Sections

### 9.2 LLM Considerations

- Both sagas use `gemini-3.1-flash-lite` for any LLM call.
- Mood parser: ≤ 128 tokens in / ≤ 64 tokens out.
- Journal structurer: ≤ 256 tokens in / ≤ 128 tokens out.

### 9.3 Observability

- Metrics: `mood_logged`, `mood_check_skipped`, `journal_prompt_offered`,
  `journal_entry_captured`.

### 9.4 Rollback Plan

- Remove sagas from dispatcher; existing JSONB data remains.

## 10. Findings & Follow-ups

### 10.1 Improvements observed / audit

- **AC-4 was NOT actually wired by task 36** (the spec claimed the TripAgent
  "already" read `live_state.last_mood` in its profile_summary). `profile_utils.py`
  had zero mood references. Fixed here, not downgraded: added
  `profile_utils.build_live_context(trip)` and injected it into
  `conversation_context` in `PlanningSaga._decide`, so the TripAgent/PlannerAgent
  receive the latest mood and adapt pacing/swaps. It surfaces on the turn AFTER
  the mood is logged (the trip is re-hydrated each turn; the orchestrator
  applies a listener's side effects to the DB, not to the in-memory trip the
  owner sees the same turn) — which matches the real UX ("felt tired" → next
  ask gets lighter options).
- **"Last 3 moods" (§4) not feasible as written.** The data model stores a
  single `live_state.last_mood` (overwritten), with no history array. Implemented
  the single most-recent mood in the context line. Follow-up: a
  `live_state.mood_history[]` (capped) if trend-awareness is wanted. Priority: low.

### 10.2 Spec deviations

- **`SagaResult.state_delta` is ignored by the orchestrator** (per-turn state is
  not persisted). The spec's `state_delta={"mood_logged_today": True}` /
  `journal_prompted_today` would be no-ops. Replaced with **persisted** signals
  on the trip: `live_state.mood_prompt_date` and `journal.last_prompt_date`
  (per-DAY, not per-session — there is no session store). This satisfies AC's
  intent ("once per day") robustly across sessions.
- **No `entities.mood`** is produced by the router. Mood capture uses a parser
  (`parse_mood`: deterministic fast-path for the LiveStateCard message shape +
  a keyword-gated `flash-lite` call for free text), not router entities.
- **`trip_patch` shape.** The spec's dotted-path `{"patch": {"live_state.last_mood": …}}`
  doesn't match `TripRepository.apply_side_effect` → `upsert_trip`, which
  merge-replaces whole JSONB sections. Implemented by pre-merging the full
  `live_state` / `journal` dict and emitting `SideEffect("trip_patch",
  {"id", "live_state"|"journal": <merged>})`.
- **Saga role (owner vs listener)** is re-derived inside `run()` via
  `should_activate(...)` rather than reading the unused `state["activation_mode"]`
  — no change to the fixed `run` signature or the orchestrator.
- **MoodCheckinSaga is listener-only** (never owns) so it can't interrupt a
  question; the once-a-day prompt is a non-blocking `status` nudge (the
  persistent widget lives in the dashboard LiveStateCard). **JournalSaga owns**
  only a low-substance CHAT turn (not prompted today); on TRIP/PLAN it listens
  so the companion answers (Constraint §5).
- **§4 file additions:** `backend/src/agentic_traveler/orchestrator/sagas/saga_state.py`
  (imported, not modified); `frontend/.../JournalSection.tsx` Save button wired
  to send the note through chat (the task-40 mood widget + journal prompt chips
  were already wired). No direct journal-write endpoint exists (chat-first);
  the Save composer sends a message the JournalSaga captures — recorded as a
  follow-up if a direct PATCH is later wanted.
- **Dispatcher registry-order test** updated for the two new sagas.

## 11. Definition of Done

- [x] AC-1 (LIVING activation), AC-2 (8 prompts ≤100 chars, day-stable),
  AC-3 (mood parse → `live_state.last_mood`), AC-4 (mood folded into
  TripAgent/Planner context — newly wired), AC-5 (REMEMBERING activation +
  once/day), AC-6 (3 journal prompts), AC-7 (structured entries +
  highlights/regrets), AC-8 (all four metrics emitted) — covered by unit tests.
- [x] Unit suite passes (`pytest`: 355 passed; +22 for the two sagas); `ruff` clean.
- [x] `npm run build` succeeds (frontend touchpoints: LiveStateCard already
  wired in task 40; JournalSection Save composer wired here).
- [ ] Mobile + desktop manual verification of the LiveStateCard mood widget and
  JournalSection composer — owed (needs the running app + a LIVING/past trip).
- [x] README updated (agent roster + the two new sagas).

## Manual operations (user, post-implementation)

1. Verify on a real trip (a fixture trip with dates spanning today → LIVING,
   or ended ≤30 days ago → REMEMBERING) that: the mood prompt status nudge
   fires once per day; tapping the LiveStateCard mood widget writes
   `live_state.last_mood` and the next companion reply adapts; a journal
   prompt is offered once per day in REMEMBERING and reflections are captured
   into `trips.journal`.
