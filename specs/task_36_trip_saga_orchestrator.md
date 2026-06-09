# Task 36 — Trip saga orchestrator (`BaseSaga` + `PlanningSaga` + dispatcher)

> Spec lineage: `specs/proposal_trip_model_and_planning_saga.md` §5, §10.6, §11.4.
> Foundation for every feature saga (tasks 38, 39, 41, 42).
> Depends on tasks 34 (trips data model) and 35 (metrics baseline).
> Absorbs the goals of the obsolete `task_guided_planning_flow.md` (progressive
> questions) and `task_chat_future_extensions.md` §1 (multiple-choice prompt
> contract — see §5.1 and §7 Step 5). Both are deleted by this task.

## 1. Problem Statement

Today the orchestrator routes every user turn through `RouterAgent.classify`
to one of `ChatAgent` / `TripAgent` / `PlannerAgent`. There is no notion of
*which trip* a turn refers to, no place to remember "this user has not yet
told me their pace for this trip", and no separation between "answer the
user's question" and "structurally update the trip object." The proposal
shows that a thin extension of the router into a **saga dispatcher**, with
each saga being a small slot-filling skill that owns one concern (planning,
discovery, country intel, booking, mood, journal), gives us multi-topic
conversation, complete data collection, and a single shape that maps 1:1
to a future LangGraph migration without paying that dependency cost today.
This task lands the saga abstraction (`BaseSaga`, `SagaState`, `SagaResult`,
`SlotRequest`) per proposal §10.6, the dispatcher logic per §5.5, the
PlanningSaga with its 7 states, and a `ChatSaga` / `OffTopicSaga` wrapping
the existing agents so the surface stays consistent. Concurrent satellite
sagas (CountryIntel, BookingInput, MoodCheckin, Journal) ship in later
tasks; this one provides their base class and the dispatcher slot.

## 2. Goals & Non-Goals

### Goals

- A new turn flows: orchestrator → `resolve_active_trip` → router →
  saga dispatcher → owner saga's `run()` → optional side-effect listener
  sagas → persist trip patches → emit metrics → reply.
- The PlanningSaga produces concise replies (per §4.1 conciseness rule),
  asks at most one clarifying question per turn (per spec 31), respects
  `user_profiles.profile_data.hard_overrides`, and writes structured
  patches to the trip via the TripRepository.
- Saga state is **derived from trip data** (`derive_saga_state` from task 34)
  — never hand-set, never drifts.
- The `EventEmitter` from task 35 is threaded through every saga and every
  agent call.
- Every saga ships with its minimum metric emission (entered / exited /
  slot_filled / error) automatically via `BaseSaga.run` instrumentation.

### Non-Goals

- Realtime DB pushes, SSE streaming, status events to the user — task 37.
  This task uses the EventEmitter's `metric` phase only; `status` and
  `delta` go to no-op sinks until task 37 wires them.
- **Rendering** the multiple-choice prompts (web chips / Telegram inline
  keyboard) and the click→`/chat/send` round-trip — task 37 + frontend.
  This task lands only the *data contract* (`SlotRequest.choices`) and the
  saga that produces it.
- The CountryIntel, BookingInput, MoodCheckin, Journal sagas — separate
  tasks 38, 39, 41.
- Curiosity prompts library — task 42. The PlanningSaga's prompt has a
  `<curiosity_prompt>` slot that defaults to empty.
- Adopting LangChain or LangGraph at runtime.

## 3. Acceptance Criteria

AC-1. `BaseSaga`, `SagaState`, `SagaResult`, `SlotRequest`, `SlotFillStatus`
  exist in `backend/src/agentic_traveler/orchestrator/sagas/base.py` with
  the exact shapes in §10.6 of the proposal (extended with `events`
  parameter per §11.4).

AC-2. `PlanningSaga` correctly computes its state from trip data using
  `derive_saga_state` (task 34's Postgres function, mirrored as a Python
  pure-function `derive_saga_state_local` for unit tests).

AC-3. When a user says *"plan my trip to Iceland"* and no prior pace /
  structure / budget / travelers info exists, the PlanningSaga asks **one**
  clarifying question (the highest-priority missing slot), not a multi-question
  block. After all four slots are filled across turns, the saga delegates
  to the PlannerAgent for the full itinerary.

AC-4. When the user has set
  `hard_overrides = [{"slot": "ask.budget", "value": "$$$", ...}]`, the
  PlanningSaga does NOT ask about budget even when missing — it uses the
  override and proceeds.

AC-5. The trip resolution order per proposal §5.5 is implemented:
  `active > ready_to_go > most-recently-updated`. When the user explicitly
  names a trip in the message, that overrides the priority order.

AC-6. Every PlanningSaga reply is ≤ 1 200 chars (default) or shorter per
  the user's `reply_length_preference`. Enforced by a hard assertion in the
  saga's `_postprocess` after the LLM returns.

AC-7. Per-turn `analytics_events` rows include: `saga_entered`,
  `saga_exited`, `turn_completed`. If a slot was asked, `slot_request_emitted`.
  If an error occurred, `error_raised`.

AC-8. The existing `OffTopicGuard` and `ChatAgent` still work, wrapped as
  `OffTopicSaga` / `ChatSaga`. No regression in behaviour for existing
  flows.

AC-9. PlanningSaga's reply test suite ("plan my Iceland trip") asserts that
  in three back-to-back turns it asks pace, then structure, then proceeds
  to delegate to PlannerAgent.

AC-10. **Drift / redirect (the user is never trapped in a slot).** When the
  active trip has an open slot but the user's turn is a question or a new
  desire (router `intent=TRIP`) rather than an answer to that slot, the
  PlanningSaga **answers** via the content engine (TripAgent) instead of
  re-asking the slot. It must NOT reply with the same slot question turn after
  turn regardless of the message. Any planning facts the user happens to
  mention are still captured as side-effects. (An explicit `intent=PLAN` turn,
  or a turn that yields new slot info, still drives slot-filling.)

## 4. Files & Modules Touched

```
backend/src/agentic_traveler/orchestrator/sagas/__init__.py          [create]
backend/src/agentic_traveler/orchestrator/sagas/base.py              [create]
backend/src/agentic_traveler/orchestrator/sagas/saga_state.py        [create]
backend/src/agentic_traveler/orchestrator/sagas/trip_resolver.py     [create]
backend/src/agentic_traveler/orchestrator/sagas/slot_extractor.py    [create — saga-local structured extraction]
backend/src/agentic_traveler/orchestrator/sagas/planning.py          [create]
backend/src/agentic_traveler/orchestrator/sagas/discovery.py         [create]
backend/src/agentic_traveler/orchestrator/sagas/chat.py              [create]
backend/src/agentic_traveler/orchestrator/sagas/off_topic.py         [create]
backend/src/agentic_traveler/orchestrator/sagas/dispatcher.py        [create]
backend/src/agentic_traveler/orchestrator/agent.py                   [modify — direct replacement of _dispatch]
backend/src/agentic_traveler/orchestrator/router_agent.py            [modify — entity extraction]
backend/src/agentic_traveler/orchestrator/profile_utils.py           [modify — add trip vision + hard_overrides + reply_length to digest]
backend/src/agentic_traveler/tools/trip_repo.py                      [modify — add apply_side_effect dispatcher]
backend/tests/orchestrator/sagas/test_saga_state.py                  [create]
backend/tests/orchestrator/sagas/test_trip_resolver.py              [create]
backend/tests/orchestrator/sagas/test_planning_saga.py              [create]
backend/tests/orchestrator/sagas/test_dispatcher.py                 [create]
specs/task_guided_planning_flow.md                                   [delete]
specs/task_chat_future_extensions.md                                 [delete — §1 absorbed into SlotRequest.choices]
specs/task_37_trip_saga_flow.md                                      [delete]
README.md                                                            [modify]
```

## 4.1 Design decisions (resolved before implementation)

These reconcile the original spec draft with what tasks 34/35 actually
shipped and with the chosen UX. See §10 for the rationale trail.

1. **Trip resolution runs on summaries, not full trips.** `TripRepository`
   exposes `list_trip_summaries()` (cheap) + `get_trip(id)` (full, 6 queries),
   not a `list_trips()`. The resolver picks a trip *id* from summaries
   (matching destination/title text), then the orchestrator hydrates **only
   that one** trip via `get_trip()`. Avoids 6×N queries per turn (cost rule).

2. **No conversation-state store.** The saga phase is derived from trip data
   (`derive_saga_state`), and the next missing slot is recomputed
   deterministically each turn, so `pending_slot` / `slots_filled` are
   *derivable* — `SagaState` is a per-turn value object, never persisted.
   The "off-topic pivot preserves the pending slot" edge case is satisfied
   for free (next planning turn recomputes the same first-missing slot).

3. **Direct replacement, no feature flag.** `_dispatch` is replaced by the
   saga dispatcher outright; rollback is `git revert`. No `SAGA_ROUTER_ENABLED`.

4. **Slot-fill progress = multiple-choice + saga-local extraction.**
   Categorical slots (`pace`, `structure`, `budget_tier`, travelers
   composition) are asked as **multiple-choice** (`SlotRequest.choices`), so
   the answer maps deterministically to the enum with zero extraction cost.
   These choices include a "Skip for now" / "N/A" option, which allows the
   user to bypass a question entirely for this specific trip without needing
   a global hard override. Free-form slots (`destination`, `timeframe`) are
   parsed by one small structured-output `flash-lite` call per planning turn 
   (`slot_extractor.py`) that also supports detecting "skip" intents. This 
   guarantees forward progress without persisting state, and absorbs
   `task_chat_future_extensions.md` §1 at the contract level.

5. **`hard_overrides` / `reply_length_preference` live at
   `user_doc["user_profile"]["profile_data"][...]`** (not directly under
   `user_profile`) — matches `profile_utils` + CLAUDE.md §7.1.

6. **`TripRepository.apply_side_effect(user_id, side_effect)`** is added to
   map `SideEffect.kind` → the existing typed upsert methods. Sagas stay
   decoupled from the repository's method surface.

## 5. Constraints

- The dispatcher must be **deterministic Python**, not an LLM call. No new
  LLM round-trip is introduced by saga selection.
- The PlanningSaga's prompt is concise, never asks two questions, never
  recaps preferences back at the user verbatim.
- Saga state must NEVER live on `self` of a saga instance. All state is in
  the `SagaState` TypedDict that the dispatcher passes in and merges back.
- Saga code must never mutate `trip` or `user_doc` in-place — only return
  `state_delta` and `side_effects` (writes the dispatcher will apply).
- The existing TripAgent / PlannerAgent / ChatAgent are reused as
  *content engines* invoked by sagas — not rewritten.
- `hard_overrides` precedence is absolute: if an override sets a slot, the
  saga never asks for it, even if other prerequisites are missing.

## 6. Edge Cases

- **User has multiple trips, none active** → trip_resolver returns the
  most recently updated one. If the user's message mentions a destination
  matching another trip, override.
- **User has zero trips** → PlanningSaga creates one in `DREAMING` on
  first user message that contains a travel-intent token. Stored in
  `side_effects`.
- **Two destinations confirmed in a multi-destination trip** → the saga
  state computes correctly off the first/earliest; multi-destination is
  supported in the schema, the saga uses the first destination for
  display purposes only.
- **Mid-saga, user pivots to off-topic** → dispatcher routes to
  `OffTopicSaga`; the planning saga's pending slot is preserved in
  `SagaState` and re-asked in the next planning turn.
- **Mid-saga, user drifts to a question / new desire (still on-topic)** → e.g.
  a trip is one slot short of complete and the user asks "what's tipping like
  in Europe?" or "I want somewhere warm with beaches". The saga must **answer**
  (delegate to TripAgent), not re-ask the open slot. This is the AC-10 rule and
  is enforced by `run()` branching on `intent=TRIP` + "no slot progress this
  turn" → delegate. Regression test in §8 (see the budget-stuck scenario).
- **Router fails to classify** → defaults to `intent=CHAT`; ChatSaga owns
  the turn.
- **Slot prompt LLM call fails** → saga returns `text` = a hand-written
  fallback "Sorry, something glitched. Try again?" and emits
  `error_raised`.
- **Trip resolver picks a trip the user didn't intend** → the user can
  always explicitly switch by naming the destination; if confusion persists,
  the dashboard's trip picker (task 40) overrides.
- **`reply_length_preference == "terse"`** → all char-budget caps reduce
  by 30 %.
- **Existing user has no `profile_data.hard_overrides` key** → treated as
  empty list; no migration needed (JSONB merges happily).

## 7. Implementation Plan

> **Note:** the code blocks below are the original illustrative draft. Where
> they conflict with §4.1 Design decisions, **§4.1 governs** — specifically:
> `SlotRequest` carries `choices`/`allow_multi`; the resolver takes summaries;
> Step 8 uses `list_trip_summaries()` + `get_trip()` + `apply_side_effect()`
> and has no `_load/_save_saga_state`; a `slot_extractor` runs before slot
> selection on each planning turn.

### Step 1 — `sagas/base.py`

```python
"""BaseSaga + state types. Matches §10.6 of the proposal verbatim.

State-as-data: never store conversation state on `self`. Slot-fill is a
return value, never an exception.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Protocol, TypedDict, Optional, runtime_checkable, Any


class SagaState(TypedDict, total=False):
    trip_id: Optional[str]
    saga_name: str
    slots_filled: dict[str, Any]
    pending_slot: Optional[str]
    history: list[str]   # short trail for the next saga turn


@dataclass(frozen=True)
class SlotRequest:
    slot: str
    prompt: str          # user-facing single question, <=200 chars


@dataclass
class SideEffect:
    """A patch the dispatcher will apply after the saga returns.
    Keep these tiny — one per logical write."""
    kind: str            # 'trip_patch' | 'destination_upsert' | 'booking_upsert' | ...
    payload: dict[str, Any]


@dataclass
class SagaResult:
    text: Optional[str] = None              # user-facing reply (owner only)
    slot_request: Optional[SlotRequest] = None
    state_delta: dict[str, Any] = field(default_factory=dict)
    side_effects: list[SideEffect] = field(default_factory=list)
    _raw_response: Any = None                # for usage_tracker
    _latency_ms: float = 0.0


@runtime_checkable
class BaseSaga(Protocol):
    name: str
    def should_activate(
        self, intent: str, entities: dict, trip: dict | None, state: SagaState
    ) -> tuple[bool, bool]:
        """(can_act, wants_to_own_reply)."""
    def run(
        self, message: str, user_doc: dict, trip: dict | None,
        state: SagaState, conversation_context: str,
        events,                              # EventEmitter from task 35
    ) -> SagaResult:
        """Pure-ish: never mutates self. Emits via events.emit('metric'|'status', ...)."""
```

### Step 2 — `sagas/saga_state.py` (state derivation, mirrors the SQL function)

```python
"""Compute saga_state from a loaded trip dict — must match
public.derive_saga_state() in task 34 exactly. Unit-tested against
shared fixtures."""

from datetime import date

STATES = ("DREAMING", "SHAPING", "ANCHORING", "DETAILING",
          "READY_TO_GO", "LIVING", "REMEMBERING")

def derive_saga_state_local(trip: dict | None, today: date | None = None) -> str:
    if trip is None:
        return "DREAMING"
    today = today or date.today()
    tf = (trip.get("discovery") or {}).get("timeframe") or {}
    start = _to_date(tf.get("start_date"))
    end   = _to_date(tf.get("end_date"))
    if start and end and start <= today <= end:
        return "LIVING"
    if end and end < today and (today - end).days <= 30:
        return "REMEMBERING"
    if start and 0 <= (start - today).days <= 7:
        return "READY_TO_GO"
    dests = trip.get("destinations") or []
    confirmed = sum(1 for d in dests if d.get("status") == "confirmed")
    considered = sum(1 for d in dests if d.get("status") == "considering")
    prefs = trip.get("preferences") or {}
    travelers = trip.get("travelers") or {}
    slots_ok = bool(
        prefs.get("pace") and prefs.get("structure")
        and prefs.get("budget_tier") and travelers.get("count")
    )
    bookings = trip.get("bookings") or []
    if bookings or (confirmed > 0 and slots_ok):
        return "DETAILING"
    if confirmed > 0 and start:
        return "ANCHORING"
    if confirmed > 0 or considered > 0:
        return "SHAPING"
    return "DREAMING"

def _to_date(s):
    if isinstance(s, date): return s
    if not s: return None
    try:
        return date.fromisoformat(str(s))
    except ValueError:
        return None
```

### Step 3 — Trip resolver

```python
# sagas/trip_resolver.py
"""Resolve which trip the current turn is about.

Priority (per proposal §5.5):
  1. user explicitly names a trip (destination string match)
  2. active trip (today in [start, end])
  3. ready_to_go trip (start <= today + 14 days, status == 'ready')
  4. most recently updated trip
  else None.
"""
def resolve_active_trip(trips: list[dict], message: str) -> dict | None:
    if not trips:
        return None
    lower = message.lower()
    # 1. explicit destination mention
    for t in trips:
        for d in (t.get("destinations") or []):
            name = (d.get("name") or "").lower()
            if name and name.split(",")[0].strip() in lower:
                return t
    # 2. active
    actives = [t for t in trips if t.get("status") == "active"]
    if actives:
        return _most_recent(actives)
    # 3. ready_to_go
    ready = [t for t in trips if t.get("status") == "ready"]
    if ready:
        return _most_recent(ready)
    # 4. most recently updated
    return _most_recent(trips)

def _most_recent(ts: list[dict]) -> dict:
    return max(ts, key=lambda t: t.get("updated_at") or "")
```

### Step 4 — Dispatcher

```python
# sagas/dispatcher.py
from .planning import PlanningSaga
from .discovery import DiscoverySaga
from .chat import ChatSaga
from .off_topic import OffTopicSaga

_SAGAS = [PlanningSaga(), DiscoverySaga(), ChatSaga(), OffTopicSaga()]

# Future tasks register: CountryIntelSaga, BookingInputSaga, MoodCheckinSaga,
# JournalSaga, MemorySearchSaga (post-alpha).

def select_sagas(intent: str, entities: dict, trip: dict | None, state):
    owner = None
    listeners = []
    for s in _SAGAS:
        can_act, wants_owner = s.should_activate(intent, entities, trip, state)
        if not can_act:
            continue
        if wants_owner and owner is None:
            owner = s
        elif not wants_owner:
            listeners.append(s)
    if owner is None:
        owner = next((s for s in _SAGAS if s.name == "ChatSaga"), None)
    return owner, listeners
```

### Step 5 — PlanningSaga — the canonical one

Skeleton:

```python
# sagas/planning.py
import time
from agentic_traveler.orchestrator.client_factory import gemini_generate
from agentic_traveler.core.observability import traceable
from agentic_traveler.orchestrator.profile_utils import build_profile_summary
from agentic_traveler.orchestrator.planner_agent import PlannerAgent
from agentic_traveler.orchestrator.trip_agent import TripAgent
from .base import BaseSaga, SagaResult, SagaState, SlotRequest, SideEffect
from .saga_state import derive_saga_state_local

_SLOT_ORDER = ["destination", "timeframe", "travelers", "pace", "structure", "budget_tier"]

_SLOT_QUESTIONS = {
    "destination": "Where are you thinking of going?",
    "timeframe":   "Roughly when?",
    "travelers":   "How many of you, and what's the makeup — solo, couple, friends, family?",
    "pace":        "Slow, medium, or punchy days?",
    "structure":   "Want it loose with anchors, or a fuller plan?",
    "budget_tier": "What feels right for budget — $, $$, $$$, $$$$?",
}

_SYSTEM_PROMPT = """\
You are the Planning Saga of Aletheia Travel. The user is building or refining
a trip with you across many turns.

You receive:
- The user's vision summary (their north star for this trip).
- The current trip state (destinations, timeframe, travelers, preferences).
- A list of hard overrides the user has previously set (NEVER ask about these).
- The conversation context (last few turns).
- The user's latest message.

Rules:
- Always reply in <= {char_cap} characters.
- Never ask more than ONE question in a turn.
- Never recap preferences back to the user verbatim. Reflect them in tone.
- Never claim authority on visas, medical, or legal facts. Use the
  "verify with official sources" language if relevant.
- Be warm, brief, and useful. No filler ("happy to help!"), no recaps, no
  emoji unless the user uses one first.

If the saga state is DREAMING or SHAPING, lean into possibilities; never
push for dates. If ANCHORING, you may ask one slot-fill question. If
DETAILING, delegate to the planner — return text that says "let me put a
plan together" and the dispatcher will invoke the PlannerAgent.
"""

class PlanningSaga(BaseSaga):
    name = "PlanningSaga"

    def __init__(self):
        self._planner = PlannerAgent()
        self._trip_agent = TripAgent()

    def should_activate(self, intent, entities, trip, state):
        if intent in ("PLAN", "TRIP"):
            return True, True   # owner
        return False, False

    @traceable(name="saga.planning.run")
    def run(self, message, user_doc, trip, state, conversation_context, events):
        t = time.time()
        events.emit("metric", {"name": "saga_entered", "saga": self.name,
                               "from": state.get("saga_name", "")})

        ss = derive_saga_state_local(trip)
        hard_overrides = self._hard_overrides(user_doc)
        char_cap = self._char_cap(user_doc, default=1200)

        # Pick the highest-priority missing slot
        missing = self._first_missing_slot(trip, hard_overrides)

        if ss == "DETAILING" or (ss == "ANCHORING" and missing is None):
            # Hand off to PlannerAgent for the full structured plan
            return self._delegate_planner(user_doc, message, conversation_context,
                                          char_cap, events, t)

        if ss in ("DREAMING", "SHAPING") or missing is None:
            # Open-ended chat-style reply via TripAgent with the saga's framing
            return self._delegate_trip_agent(user_doc, message, conversation_context,
                                             trip, char_cap, events, t)

        # Slot-fill: ask ONE question
        return self._ask_slot(missing, char_cap, events, t)

    # … helpers: _first_missing_slot, _hard_overrides, _char_cap,
    # _delegate_planner, _delegate_trip_agent, _ask_slot. Each ≤ 30 LoC.
```

Helper bodies:

```python
def _first_missing_slot(self, trip, overrides):
    """Return the highest-priority _SLOT_ORDER slot that is missing AND not
    satisfied by a hard override. None if all filled."""
    if trip is None:
        return "destination"
    filled = self._slot_values(trip)
    for slot in _SLOT_ORDER:
        if slot in overrides:
            continue
        if not filled.get(slot):
            return slot
    return None

def _slot_values(self, trip):
    return {
        "destination": any(d.get("status") == "confirmed"
                           for d in (trip.get("destinations") or [])),
        "timeframe":   bool((trip.get("discovery", {}).get("timeframe") or {}).get("start_date")),
        "travelers":   bool((trip.get("travelers") or {}).get("count")),
        "pace":        (trip.get("preferences") or {}).get("pace"),
        "structure":   (trip.get("preferences") or {}).get("structure"),
        "budget_tier": (trip.get("preferences") or {}).get("budget_tier"),
    }

def _hard_overrides(self, user_doc):
    """Return a dict[slot] = value."""
    overrides = (user_doc.get("user_profile", {}) or {}).get("hard_overrides", []) or []
    out = {}
    for o in overrides:
        slot = (o.get("slot") or "")
        if slot.startswith("ask."):
            slot = slot.removeprefix("ask.")
        out[slot] = o.get("value")
    return out

def _char_cap(self, user_doc, default):
    pref = (user_doc.get("user_profile", {}) or {}).get("reply_length_preference", "default")
    if pref == "terse":   return int(default * 0.7)
    if pref == "verbose": return int(default * 1.4)
    return default

def _ask_slot(self, slot, char_cap, events, t):
    q = _SLOT_QUESTIONS[slot]
    events.emit("metric", {"name": "slot_request_emitted", "slot": slot})
    events.emit("metric", {"name": "saga_exited", "saga": self.name,
                           "outcome": "slot_request",
                           "latency_ms": (time.time() - t) * 1000})
    return SagaResult(slot_request=SlotRequest(slot=slot, prompt=q), text=q)
```

The `_delegate_*` helpers wrap the existing TripAgent/PlannerAgent
`process_request` calls in `@traceable` and re-cap the response to
`char_cap` if the LLM ran long (truncate + ellipsis last word, log a WARN).

### Step 6 — DiscoverySaga / ChatSaga / OffTopicSaga (thin wrappers)

`DiscoverySaga` activates on `intent=TRIP` when no trip is resolved yet —
delegates to `TripAgent`. Side-effect: when destination candidates appear
in the response, write them to `trip.discovery.destinations` with
`status='considering'`.

`ChatSaga` always-acts-as-listener, owns when intent=CHAT.

`OffTopicSaga` always-acts, owns when intent=OFF_TOPIC. Wraps existing
`off_topic_guard`.

### Step 7 — RouterAgent: extend entity extraction

The router's existing JSON schema gains an `entities` object:

```json
{
  "intent": "TRIP|PLAN|CHAT|OFF_TOPIC",
  "request_summary": "...",
  "preference_updated": {"key": "...", "value": "..."} | null,
  "response": "...",
  "entities": {
    "destinations":  ["Iceland"],
    "season":        "winter" | null,
    "month":         "January" | null,
    "dates":         {"start": "2027-01-22", "end": "2027-01-30"} | null,
    "mood":          "tired" | "energetic" | null,
    "booking_shaped": true | false,
    "named_trip":    "Kyoto" | null
  }
}
```

Prompt addition: a short paragraph telling the router to extract those
entities verbatim — keep terse, do not invent.

### Step 8 — Orchestrator wiring

`_process_user_doc` becomes:

```python
# 1. credit gate, restriction gate, build context (unchanged)
# 2. resolve trips
trips = trip_repo.list_trips(user_id)
trip = resolve_active_trip(trips, message_text)
# 3. router (entity-extended)
router_result = self._router.classify(...)
# 4. saga state (loaded from trip if exists)
state = self._load_saga_state(user_id)
# 5. select owner + listeners
owner, listeners = select_sagas(intent, entities, trip, state)
# 6. build EventEmitter
events = EventEmitter(user_id=user_id, trip_id=trip and trip["id"], on_status=None, on_delta=None)
# 7. listeners run first (idempotent side-effects)
for s in listeners:
    s.run(message_text, user_doc, trip, state, conv_context, events)
# 8. owner runs
result = owner.run(message_text, user_doc, trip, state, conv_context, events)
# 9. apply side effects (write to trip via TripRepository)
for se in result.side_effects:
    trip_repo.apply_side_effect(se)
# 10. merge state_delta back, persist saga_state pointer
self._save_saga_state(user_id, {**state, **result.state_delta})
# 11. emit turn_completed, flush metrics
events.emit("metric", {"name": "turn_completed",
                       "latency_ms": (time.time() - t0)*1000,
                       "credits": cost, "intent": intent,
                       "owner_saga": owner.name})
events.flush_metrics()
# 12. persist message + deduct credits (unchanged)
```

### Step 9 — Profile digest update

`build_profile_summary()` gains three new fields it embeds:

- Active trip vision (one line).
- `hard_overrides` summarised as "Never ask about: X, Y".
- `reply_length_preference`.

### Step 10 — Tests

`test_planning_saga.py`:
- Each saga state path (DREAMING/SHAPING/ANCHORING/DETAILING/LIVING/REMEMBERING)
  routes to the expected helper.
- Slot ordering: destination → timeframe → travelers → pace → structure → budget.
- `hard_overrides` skips the matching slot.
- Char-cap enforcement: when the LLM mock returns 2000 chars, the saga
  truncates to the cap and emits a WARN log.
- Conciseness: each slot prompt asserts `len(prompt) <= 200`.

`test_dispatcher.py`: each intent maps to the expected owner + listeners.

`test_trip_resolver.py`: priority order; explicit destination override.

## 8. Testing Plan

- **Unit:** every saga's `should_activate` table, slot ordering, override
  precedence, char-cap, derive_saga_state_local parity with the SQL fixture.
- **Integration:** end-to-end planning flow ("plan my Iceland trip"
  → 3 turns → full itinerary) against real Supabase + mocked Gemini.
- **Manual:** the eight named planning scenarios from
  `frontend_dashboard_design.md` §6 Trip Lifecycle.

Sample expected output:

```
Turn 1 (user): "Plan my trip to Iceland in late January"
Bot: "Iceland in late Jan is striking. How many of you?"
       (slot=travelers, len=46)

Turn 2 (user): "Two — me and my partner"
Bot: "Slow days, medium, or packed?"
       (slot=pace, len=33)
```

## 9. Conditional Sections

### 9.2 LLM Considerations

- **Model tier:** the PlanningSaga's own prompt uses `gemini-3.5-flash`
  for reasoning quality (it makes saga-routing-style decisions).
  Delegated calls to TripAgent/PlannerAgent use their existing models.
- **Token budget per call:** input ≤ 1500 (profile summary + trip digest +
  conversation context + message), output ≤ 600 (with char-cap of 1200 hard
  ceiling).
- **Prompt-injection surface:** `message`, `conversation_context`,
  `vision_summary`. All wrapped in `<…>` XML-style fences in the prompt;
  router has already run intent classification so we know it's not a tool
  exfiltration attempt.
- **Tool definitions:** the saga itself adds no new tools to the LLM.
  Tools come from the delegated agents (TripAgent/PlannerAgent already
  have weather + search).
- **Versioning:** prompt string is constant at module top; changes are git-
  diffable.

### 9.3 Observability

- Per-turn metrics: `saga_entered`, `saga_exited`, `slot_request_emitted`,
  `turn_completed` (orchestrator), `error_raised` on failure.
- LangSmith `@traceable` on each saga's `run`.
- Char-cap-exceeded logs at WARN with the over-length count.

### 9.4 Rollback Plan

- **Direct replacement** (§4.1 #3): `_dispatch` is replaced by the saga
  dispatcher; rollback is `git revert` of the `agent.py` change. No feature
  flag is carried.
- No schema rollback needed — sagas only read/write existing trips columns;
  no new tables or columns are introduced.

## 10. Findings & Follow-ups

### 10.1 Findings (noticed but not changed)

- The repo had **two numbering lineages** that had drifted: filename numbers
  (`task_27`, `task_23`) vs. title/code identities ("Task 36" = auth-id merge,
  "Task 37" = account settings). This task renumbered the saga lineage by
  filename (shift-by-11: 45→34 … 53→42) and, per user direction, corrected the
  drifted titles + code comments so each task number is unique again
  (`task_27` title/comments → "Task 27"; `task_23` title → "Task 23"). The
  stale "LangSmith (task 44)" reference in `task_35` was left as-is (out of
  scope; not a collision).

### 10.2 Spec deviations (from the original task_47 draft)

- `trip_repo.list_trips()` (assumed) does not exist → resolver uses
  `list_trip_summaries()` + `get_trip()` hydrate (§4.1 #1).
- `trip_repo.apply_side_effect()` added (§4.1 #6).
- `_load_saga_state`/`_save_saga_state` removed — no conversation-state store
  (§4.1 #2). Step 8's saga-state-pointer persistence is dropped.
- `SAGA_ROUTER_ENABLED` feature flag dropped in favour of direct replacement
  (§4.1 #3, per user decision).
- `SlotRequest` gained `choices` + `allow_multi` (multiple-choice contract,
  absorbing `task_chat_future_extensions.md` §1).
- `slot_extractor.py` added — the original draft had no mechanism to write the
  user's free-text slot answer back to the trip (infinite re-ask loop). §4.1 #4.
- `hard_overrides` / `reply_length_preference` read path corrected to
  `user_profile.profile_data.*` (§4.1 #5).
- `derive_saga_state_local` tests key-*presence* (`'pace' in prefs`) to match
  the SQL's `preferences ? 'pace'` exactly (AC-2 parity).
- Tests placed under `backend/tests/orchestrator/sagas/` (existing convention),
  not flat `backend/tests/`.
- **Post-ship fix — "stuck on a slot, can't drift" (AC-10 added).** A live user
  (Supabase `82d7409a-3933-451f-abd2-2e947d69be93`) hit a trip with every slot
  filled except `budget_tier`; the saga replied "What's the budget vibe?" to a
  tipping question, a "somewhere warm with beaches" desire, and "let's plan a
  trip to Tokyo" alike. Root cause: `run()` did `if missing is not None:
  ask_slot` **unconditionally**, so any open slot trapped every turn. Fix:
  `run()` now branches on `intent`/progress — when `intent=TRIP` and the turn
  produced no slot progress, it delegates to TripAgent (answers the user)
  instead of re-asking; `intent=PLAN` or a turn with new slot info still
  slot-fills. Added AC-10, a §6 drift edge case, and four `test_planning_saga`
  drift tests mirroring the real user's trip state. This realigns the saga with
  the task goal "allow the user to drift to whatever he wants."
- A categorical-slot **`skip`** option was added to `_SLOT_CHOICES` /
  `slot_extractor` (key-presence marks the slot satisfied, so the saga advances
  past a skipped slot); `should_activate` intercepts CHAT-misclassified button
  values via `_CHOICE_VALUES` derived from `_SLOT_CHOICES`.

## 11. Definition of Done

- [ ] ACs 1–10 pass.
- [ ] Existing chat / trip / planner flow regression suite passes.
- [ ] `task_guided_planning_flow.md`, `task_chat_future_extensions.md`, and
  `task_37_trip_saga_flow.md` deleted (superseded/absorbed).
- [ ] `ruff` clean; `pytest` passes.
- [ ] README updated to describe the saga architecture at a high level.

## Manual operations (user, post-implementation)

None. The superseded spec files are removed in this same change; rollback is
`git revert`. No env-var toggle and no manual migration step.
