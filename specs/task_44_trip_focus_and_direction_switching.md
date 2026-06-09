# Task 44 — Trip focus & direction-switching: thoughtful sagas, user-led pivots

> Spec lineage: `specs/task_36_trip_saga_orchestrator.md` (saga dispatch +
> `resolve_active_trip` + state-as-data) and the §7.1 invariant "user message
> dictates what happens." Builds on the task-37 follow-up that gated the heavy
> PlannerAgent behind explicit intent. Soft-blocks nothing; **benefits** task 43
> (the confirmation becomes a tappable two-option chip once 43 lands).

## 1. Problem Statement

A user with established trips typed **"I want to plan a trip"** expecting to
start a *new* planning flow. Instead the system silently bound the turn to an
existing, fully-slotted trip and ran the heavy PlannerAgent, returning a full
(and partly hallucinated) day-by-day itinerary for a destination the user never
mentioned. LangSmith trace: `router.classify` → `PLAN`, `resolve_active_trip`
picked the most-recent established trip, `PlanningSaga` saw all slots filled +
`intent == PLAN` → `PlannerAgent` (21 s, multiple searches) → itinerary.

Two capabilities are missing:

1. **No "new trip" / "switch trip" signal.** `resolve_active_trip` greedily maps
   *any* planning turn to a trip (explicit name → active → ready → most-recent).
   A generic request with no destination falls through to "most-recent," so the
   user can never express "a *different*/new one" — the system assumes "this one."
2. **No disambiguation pause.** When the request is generic *and* an established
   trip is in focus, the saga acts immediately instead of confirming direction.
   There is no "we're mid-way on **Japan** — keep going, or start fresh?" step.

The desired behaviour (user's words): *at most a confirmation* — e.g. "We were
finishing trip X — want to start a new one?" or, on an explicit new-trip
request, "Putting **Japan** on hold; let's start planning a new one — where to?"
The saga's structure should still guide the user, but the **user's message must
be able to redirect it at any time** (continue / switch / start new), without a
big computation firing on the wrong trip.

## 2. Goals & Non-Goals

### Goals

- The Router emits a `trip_directive ∈ {continue, new, unspecified}` for
  travel-planning turns (one extra enum on the **existing** router call — no new
  model call), distinguishing "keep working on a trip" from "start a new/
  different one" from "generic, target unclear."
- Trip resolution honours the directive: `new` never binds to an existing trip
  (it creates a fresh one and records which trip, if any, was set aside);
  `continue`/`unspecified` resolve as today.
- The PlanningSaga **confirms direction** instead of acting when the request is
  generic (`unspecified` + `PLAN`) and an **established** trip is in focus —
  returning a short either/or message, no plan generated, no slot-fill mutation.
- An explicit **new-trip** turn proceeds but **acknowledges** the trip put on
  hold ("Putting **<title>** on hold — let's start fresh. Where to?").
- The heavy PlannerAgent on a fully-slotted trip runs only when the user is
  actually continuing/refining it (`continue`, or a new planning fact this turn),
  never on a generic/ambiguous turn.
- Entirely **stateless**: the confirmation's answer changes the directive on the
  next turn, which changes resolution/creation, which the saga simply follows —
  no persisted "pending confirmation" flag (consistent with task 36 state-as-data).

### Non-Goals

- A new `trips.status` value for "on hold" — "on hold" is implicit (not the
  most-recently-updated trip). No schema change.
- Multi-trip pickers / listing every trip as options (the confirmation is binary:
  continue the in-focus trip, or start new). Richer trip switching is a follow-up.
- The tappable rendering of the confirmation — that rides task 43 once it lands;
  until then the confirmation is plain text and the user answers in free text
  (which the router re-classifies as `continue`/`new`).
- Fixing the PlannerAgent's destination grounding/hallucination in general (it
  invented Malibu here only because it should never have run; out of scope).

## 3. Acceptance Criteria

AC-1. The Router result includes `trip_directive` ∈ {`continue`,`new`,
  `unspecified`}; it defaults to `unspecified` on parse failure or for non-travel
  intents. The value is surfaced into the per-turn `SagaState` as
  `state["trip_directive"]`.

AC-2. `trip_directive == "new"` makes the orchestrator **ignore** existing trips
  and create a fresh `DREAMING` trip for the turn, even when an established trip
  exists. If a most-recent established trip existed, its title is passed as
  `state["superseded_trip_title"]`.

AC-3. With `trip_directive == "unspecified"`, `intent == "PLAN"`, the resolved
  trip **established** (has ≥1 destination), and no new planning fact supplied
  this turn, `PlanningSaga.run` returns a **confirmation** — `SagaResult.text`
  names the in-focus trip and offers continue-vs-new — with **no** `PlannerAgent`
  call and **no** slot mutation (`side_effects == []`, `slot_request is None`).

AC-4. On a `new`-directive turn that supersedes an established trip, the saga's
  first prompt **acknowledges** the set-aside trip by title and then asks the
  first missing slot (destination for a blank trip).

AC-5. A fully-slotted trip with `trip_directive == "continue"` (or with a new
  planning fact this turn) still delegates to `PlannerAgent`. A fully-slotted
  trip with `unspecified` + casual `TRIP` question still drifts to `TripAgent`
  (task-37 follow-up behaviour preserved).

AC-6. No established trip in focus (no trips, or only blank `DREAMING` trips):
  `unspecified` + `PLAN` does **not** confirm — it proceeds to slot-fill (ask
  destination) as today. No annoying confirmation when there's nothing to set
  aside.

AC-7. The confirmation message is concise (≤ 320 chars, CLAUDE.md §7.1 chat-ack
  budget) and names the in-focus trip.

AC-8. Metrics: a `trip_focus_resolved` row is emitted per planning turn with
  `{directive, outcome}` where `outcome ∈ {confirm_switch, new_trip,
  continue, slot_fill, plan}`.

AC-9. Round-trip is stateless: after a `unspecified` confirmation, a follow-up
  "start a new one" (router → `new`) creates a fresh trip and asks destination;
  a follow-up "keep going" (router → `continue`) resumes the in-focus trip — no
  persisted confirmation state involved.

## 4. Files & Modules Touched

```
backend/src/agentic_traveler/orchestrator/router_agent.py            [modify — trip_directive in schema, prompt, parse, result]
backend/src/agentic_traveler/orchestrator/agent.py                   [modify — read directive; new-trip path; thread directive + superseded title into state; metric]
backend/src/agentic_traveler/orchestrator/sagas/trip_resolver.py     [modify — resolve_trip_focus(...): directive-aware; is_established helper]
backend/src/agentic_traveler/orchestrator/sagas/planning.py          [modify — confirmation gate, new-trip ack, planner gate by directive]
backend/src/agentic_traveler/orchestrator/sagas/base.py              [modify — document trip_directive + superseded_trip_title on SagaState]
backend/tests/orchestrator/test_router_agent_directive.py            [create — directive parse/default]
backend/tests/orchestrator/sagas/test_trip_resolver.py               [modify — directive-aware resolution + is_established]
backend/tests/orchestrator/sagas/test_planning_saga.py               [modify — confirm gate, new-trip ack, planner-by-directive]
backend/tests/orchestrator/test_orchestrator.py                      [modify — new-trip creation path + state threading]
README.md                                                            [modify — saga section: direction-switching + confirmation]
specs/task_44_trip_focus_and_direction_switching.md                  [this spec]
```

No schema migration; no new table; no RLS change.

## 5. Constraints

- **No new LLM call.** `trip_directive` is one enum added to the router's
  existing structured-output schema; the router already runs every turn with
  recent conversation context (enough to read "yes, a new one" after a confirm).
- **Stateless (task 36 §4.1).** No persisted "awaiting confirmation" field; the
  directive on the *next* turn drives behaviour. Nothing stored on `self`.
- **Don't over-trigger confirmations.** Only `unspecified` + `PLAN` + an
  *established* trip confirms. Casual TRIP questions, blank trips, and explicit
  continue/new turns never pause to confirm.
- **Conciseness invariant (CLAUDE.md §7.1):** confirmation ≤ 320 chars; assert
  in a test.
- **Backwards compatible:** a missing/`unspecified` directive reproduces today's
  resolution for the common case (one in-progress trip, explicit references).
- CLAUDE.md §9: no auto-deploy, Gemini mocked in unit tests, no PII in logs.

## 6. Edge Cases

- **No trips at all** + `unspecified`/`new` PLAN → zero-trip path creates a
  `DREAMING` trip → ask destination. No confirmation (nothing to set aside).
- **Only blank DREAMING trips** (no destinations) + `unspecified` → not
  established → no confirm → continue slot-fill on the existing blank trip.
- **Explicit new with a destination** ("plan a new trip to Tokyo"): `new` +
  `entities.destinations=[Tokyo]` → create fresh trip, the normal slot extractor
  seeds Tokyo, proceed; brief ack, no confirm.
- **User keeps being generic** (answers a confirmation with another vague line):
  router stays `unspecified` → confirm again. Acceptable (no loop state).
- **`continue` with multiple established trips, no name** → most-recent (as
  today). User can name one to disambiguate.
- **Directive says `new` but resolution finds no established trip** → just create
  a fresh trip, no "on hold" ack (nothing was set aside).
- **Misclassification** (generic plan-start tagged `TRIP` not `PLAN`) → existing
  task-37 drift sends it to `TripAgent`, which answers conversationally — not a
  regenerated itinerary. Degrades gracefully; the bug (heavy plan on wrong trip)
  cannot recur.

## 7. Implementation Plan

### Step 1 — Router emits `trip_directive`
`router_agent.py`: add a nullable `trip_directive` enum
(`continue|new|unspecified`) to `_response_schema()`; add a STEP to
`_SYSTEM_PROMPT` (only meaningful for TRIP/PLAN; default `unspecified`); parse +
normalise in `_parse` (invalid → `unspecified`); include in the `classify`
result and the exception fallback. Prompt guidance + examples:
  - `new`: "plan a new trip", "let's start a different one", "forget that, somewhere else", and **after** the assistant asked "continue or start new?" the user choosing the new option ("a new one", "start fresh").
  - `continue`: "finish my Japan plan", "let's keep going", "yes, continue", "back to the Rome trip".
  - `unspecified`: "I want to plan a trip", "help me plan something", no clear target.
→ verify: `test_router_agent_directive.py` parses each value and defaults safely.

### Step 2 — Directive-aware focus resolution
`trip_resolver.py`: add
```python
def is_established(trip_summary: dict) -> bool:
    """A trip worth not clobbering: it already has a destination."""
    return bool(trip_summary.get("has_destinations") or trip_summary.get("destinations"))

def resolve_trip_focus(summaries, message, entities, directive):
    """Return (chosen_summary | None, superseded_title | None, create_new: bool)."""
    if directive == "new":
        prior = _most_recent([s for s in summaries if is_established(s)]) if summaries else None
        return None, (prior.get("title") if prior else None), True
    chosen = resolve_active_trip(summaries, message, entities)  # unchanged path
    return chosen, None, False
```
(Trip summaries already expose `vision_summary`/`title`/`status`; add a cheap
`has_destinations`/destination count to the summary select if not present, or
infer from title — pick the smallest change in `TripRepository.list_trip_summaries`.)
→ verify: resolver tests for `new` (ignores existing, reports superseded title),
`continue`/`unspecified` (delegates to `resolve_active_trip`), `is_established`.

### Step 3 — Orchestrator wiring (`agent.py _dispatch_sagas`)
- Read `directive = router_result.get("trip_directive", "unspecified")`.
- Replace the direct `resolve_active_trip(...)` call with `resolve_trip_focus(...)`.
- `create_new` → `trip = trip_repo.upsert_trip(user_id, {})`; set
  `state["trip_directive"]`, `state["superseded_trip_title"]`.
- Keep the existing zero-trip creation for planning/discovery owners.
- Emit a `trip_focus_resolved` metric (`{directive, outcome}`) — `outcome` is set
  by the saga's chosen branch (pass it back via `SagaResult.state_delta` or infer
  from the result). Simplest: the saga emits it.
→ verify: orchestrator test asserts a `new` directive creates a trip and threads
the superseded title.

### Step 4 — PlanningSaga: confirmation gate + ack + planner gate
In `run()`, after computing `phase`, `missing`, `intent`, `made_progress`, read
`directive = state.get("trip_directive", "unspecified")` and
`superseded = state.get("superseded_trip_title")`.

```python
# Generic plan-start against an established trip → confirm direction, don't act.
established = bool((trip or {}).get("destinations"))
if (intent == "PLAN" and directive == "unspecified"
        and established and not made_progress and phase not in ("LIVING","REMEMBERING")):
    return self._confirm_switch(trip, events, t)   # text only, no plan, no slots
```
- `_confirm_switch`: "We're mid-way on **<title>** — want to keep refining that,
  or start a brand-new trip?" (≤ 320 chars, names the trip). Emits
  `saga_exited{outcome:"confirm_switch"}`.
- New-trip ack: when `superseded` is set and the trip is blank, prepend
  "Putting **<superseded>** on hold — let's start fresh. " to the destination
  slot question (in `_ask_slot`, or compute the prefix in `run`).
- Fully-slotted gate (refine the task-37 follow-up): delegate to PlannerAgent
  when `directive == "continue" or made_progress`; else `TripAgent`. (`PLAN` +
  `unspecified` + established was already intercepted by the confirm gate above;
  `PLAN` + `continue` → planner.)
→ verify: planning-saga tests (below).

### Step 5 — Docs + metric
- README saga section: a sentence on direction-switching (continue/new/confirm)
  and the "on hold" acknowledgement.
- Register `trip_focus_resolved` in the metric catalogue / spec §9.3.

## 8. Testing Plan

- **Unit (router):** `trip_directive` parses `continue|new|unspecified`; invalid
  → `unspecified`; absent → `unspecified`; exception fallback carries it.
- **Unit (resolver):** `new` ignores existing + returns superseded title +
  `create_new=True`; `continue`/`unspecified` delegate unchanged; `is_established`.
- **Unit (PlanningSaga):**
  - `unspecified`+`PLAN`+established+no-progress → confirmation (no planner call,
    `slot_request is None`, `side_effects == []`, text names the trip, ≤ 320).
  - `new` + `superseded_trip_title` set + blank trip → first prompt acks the old
    trip and asks destination.
  - `continue` + fully-slotted → planner.
  - `unspecified` + established + casual TRIP question (no progress) → TripAgent
    drift (unchanged).
  - `unspecified`+`PLAN`+**blank** trip → asks destination, no confirmation (AC-6).
- **Unit (orchestrator):** `new` directive → `upsert_trip` called, state carries
  `trip_directive` + `superseded_trip_title`.
- **Sample happy path (web):**
  - `POST /chat/send {"body":"I want to plan a trip"}` (with an established Japan
    trip) → reply confirms: "We're mid-way on **Japan** — keep refining, or start
    fresh?" No itinerary.
  - `POST /chat/send {"body":"start a new one"}` → router `new` → fresh trip →
    "Putting **Japan** on hold — let's start fresh. Where to?".
  - `POST /chat/send {"body":"keep going on Japan"}` → router `continue` → resumes
    the Japan trip (slot-fill or plan).

## 9. Conditional Sections

### 9.2 LLM Considerations
- One enum field on the **existing** router (`gemini-3.1-flash-lite`) — no extra
  call, negligible token cost. The router already receives recent conversation
  context, so "a new one" after a confirmation is classifiable as `new`.
- The directive value never enters a downstream prompt verbatim; it only steers
  deterministic Python branches (no injection surface).

### 9.3 Observability
- `trip_focus_resolved {directive, outcome}` per planning turn.
- The existing `saga_entered`/`saga_exited` gain `outcome:"confirm_switch"` and
  `outcome:"new_trip"` values.
- Confirmations and new-trip creations logged at INFO with `user_id` + trip id
  (no PII).

### 9.4 Rollback Plan
- Additive + behavioural. Revert the diff: the router stops emitting the enum,
  the orchestrator falls back to `resolve_active_trip`, the saga loses the
  confirm gate. No schema/data migration to undo.

## 10. Findings & Follow-ups

### 10.1 Improvements observed (not done here)
- **PlannerAgent destination grounding.** In the bug trace the planner invented
  Malibu while the trip's destinations were Pitești/Baltic. Once it only runs on
  the correct trip this is moot for *this* case, but the planner prompt could
  still anchor harder on the trip's confirmed destinations. Separate task.
- **Trip picker.** A binary continue/new confirmation covers the reported case;
  switching directly to a *named third* trip relies on the user naming it. A
  multi-trip chooser (esp. once task 43 chips exist) is a future nicety.

### 10.2 Spec deviations
- **Confirmation fires only on a COMPLETE trip, not merely an "established"
  (destination-having) one.** A trip mid-slot-fill (e.g. missing budget) must
  keep collecting on a PLAN turn, not pause to ask "new or continue?". So the
  confirm gate lives in the all-essentials-known branch (`missing is None`),
  where the trip is unambiguously complete and a generic plan request is the
  ambiguous "regenerate vs new" case. `_is_established` on the summary is still
  used by the resolver to pick which trip is *superseded* by a `new` turn.
- **`is_established(summary)` uses `status` + `vision_summary`** (already in the
  `list_trip_summaries` select) rather than a destination count — no query/schema
  change (resolves Open Question §12.2).
- **`trip_focus_resolved` metric** carries `outcome ∈ {companion, slot_fill,
  new_trip, confirm_switch, plan}` (slightly richer than the spec's draft set);
  extra metric fields nest under the EventEmitter row's `payload`.
- **Planner gate keyed on `directive == "continue"` (or `made_progress`)**, not
  `intent == "PLAN"` — an explicit PLAN with `unspecified` directive on a complete
  trip is intercepted by the confirm gate first, so only a genuine continue/refine
  reaches the planner.
- Confirmation is **plain text** (free-text answer re-classified next turn); the
  tappable two-option chip lands with task 43 (Open Question §12.1, as planned).

## 11. Definition of Done

- [x] AC-1..AC-9 pass (AC-1..AC-8 unit-tested; AC-9 statelessness holds by
  construction — verified by the round-trip test design; live UI check owed).
- [x] §6 edge cases covered (blank-trip no-confirm, new-without-established,
  mid-slot-fill, misclassification drift) or deferred in §10.2.
- [x] `ruff check` clean on changed files; `pytest` unit suite passes (278).
- [x] README saga section updated.
- [x] No file outside §4 modified (also touched `sagas/base.py` to document the
  two new `SagaState` fields — additive, noted here).
- [x] No secrets/PII in logs; Gemini mocked in tests.

## 12. Open Questions

- **Confirmation as text now vs. waiting for task-43 chips.** Spec'd as plain
  text now (free-text answer re-classified next turn), upgraded to a two-option
  chip when task 43 lands. Confirm this ordering.
- **`has_destinations` on the summary.** Cheapest source: add a boolean/count to
  `list_trip_summaries`'s select, or infer "established" from `vision_summary`
  presence. Confirm the trip-summary shape before Step 2.
