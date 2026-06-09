"""PlanningSaga unit tests (Task 36).

Agents and the slot extractor are mocked — no DB / LLM. Uses a real
EventEmitter and inspects its metric buffer.
"""

from unittest.mock import MagicMock, patch

import pytest

from agentic_traveler.orchestrator.event_emitter import EventEmitter
from agentic_traveler.orchestrator.sagas.base import ChoiceOption, SideEffect, SlotRequest
from agentic_traveler.orchestrator.sagas.planning import (
    _SLOT_QUESTIONS,
    PlanningSaga,
    slot_selection_to_side_effect,
)

_EXTRACT = "agentic_traveler.orchestrator.sagas.planning.extract_trip_slots"


@pytest.fixture
def saga():
    with patch("agentic_traveler.orchestrator.sagas.planning.PlannerAgent"), \
         patch("agentic_traveler.orchestrator.sagas.planning.TripAgent"):
        s = PlanningSaga(client=MagicMock())
    s._planner = MagicMock()
    s._trip_agent = MagicMock()
    s._planner.process_request.return_value = {
        "text": "Here is your day-by-day plan.",
        "_raw_response": None, "_latency_ms": 1.0, "_search_responses": [],
    }
    s._trip_agent.process_request.return_value = {
        "text": "Some destination ideas.",
        "_raw_response": None, "_latency_ms": 1.0, "_search_responses": [],
    }
    return s


def _events():
    return EventEmitter(user_id="u1", trip_id="t1")


def _trip(**kw):
    base = {
        "id": "t1", "status": "dreaming",
        "discovery": {}, "preferences": {}, "travelers": {},
        "destinations": [], "bookings": [],
    }
    base.update(kw)
    return base


# ---------------------------------------------------------------------------
# slot ordering + overrides
# ---------------------------------------------------------------------------

def test_first_missing_slot_walks_priority_order(saga):
    assert saga._first_missing_slot(None, {}) == "destination"
    t = _trip(destinations=[{"name": "Iceland", "status": "considering"}])
    assert saga._first_missing_slot(t, {}) == "timeframe"
    t["discovery"] = {"timeframe": {"text": "late Jan"}}
    assert saga._first_missing_slot(t, {}) == "travelers"
    t["travelers"] = {"count": 2}
    assert saga._first_missing_slot(t, {}) == "pace"
    t["preferences"] = {"pace": "slow"}
    assert saga._first_missing_slot(t, {}) == "structure"
    t["preferences"]["structure"] = "loose"
    assert saga._first_missing_slot(t, {}) == "budget_tier"
    t["preferences"]["budget_tier"] = "$$"
    assert saga._first_missing_slot(t, {}) is None


def test_hard_override_skips_slot(saga):
    t = _trip(
        destinations=[{"name": "Iceland", "status": "considering"}],
        discovery={"timeframe": {"text": "late Jan"}},
        travelers={"count": 2},
        preferences={"pace": "slow", "structure": "loose"},
    )
    # budget missing, but overridden → no slot is missing.
    assert saga._first_missing_slot(t, {"budget_tier": "$$$"}) is None


# ---------------------------------------------------------------------------
# slot prompts + choices (AC-6 conciseness, multiple-choice contract)
# ---------------------------------------------------------------------------

def test_all_slot_prompts_under_200_chars():
    for prompt in _SLOT_QUESTIONS.values():
        assert len(prompt) <= 200


def test_pace_slot_is_multiple_choice(saga):
    t = _trip(
        destinations=[{"name": "Iceland", "status": "considering"}],
        discovery={"timeframe": {"text": "late Jan"}},
        travelers={"count": 2},
    )
    with patch(_EXTRACT, return_value={}):
        result = saga.run("two of us", {}, t, {}, "", _events())
    assert result.slot_request is not None
    assert result.slot_request.slot == "pace"
    assert result.slot_request.choices is not None
    assert [c.value for c in result.slot_request.choices] == ["slow", "medium", "fast", "skip"]


def test_destination_slot_is_free_text(saga):
    with patch(_EXTRACT, return_value={}):
        result = saga.run("help me plan", {}, _trip(), {}, "", _events())
    assert result.slot_request.slot == "destination"
    assert result.slot_request.choices is None


# ---------------------------------------------------------------------------
# routing
# ---------------------------------------------------------------------------

def _trip_fully_slotted():
    return _trip(
        destinations=[{"name": "Iceland", "status": "considering"}],
        discovery={"timeframe": {"text": "late Jan"}},
        travelers={"count": 2},
        preferences={"pace": "slow", "structure": "loose", "budget_tier": "$$"},
    )


def test_continue_directive_on_full_trip_delegates_to_planner(saga):
    # "continue" on a fully-slotted trip → build/refine the itinerary.
    with patch(_EXTRACT, return_value={}):
        result = saga.run(
            "build my itinerary", {}, _trip_fully_slotted(),
            {"intent": "PLAN", "trip_directive": "continue"}, "", _events(),
        )
    saga._planner.process_request.assert_called_once()
    saga._trip_agent.process_request.assert_not_called()
    assert result.text == "Here is your day-by-day plan."


# ---------------------------------------------------------------------------
# task 44 — direction switching (confirm / new / continue)
# ---------------------------------------------------------------------------

def test_generic_plan_on_complete_trip_confirms_direction(saga):
    # "I want to plan a trip" (PLAN + unspecified) on a COMPLETE established trip
    # must CONFIRM — never silently regenerate that trip's itinerary.
    events = _events()
    with patch(_EXTRACT, return_value={}):
        result = saga.run(
            "I want to plan a trip", {}, _trip_fully_slotted(),
            {"intent": "PLAN", "trip_directive": "unspecified"}, "", events,
        )
    saga._planner.process_request.assert_not_called()
    saga._trip_agent.process_request.assert_not_called()
    assert result.slot_request is None
    assert result.side_effects == []
    assert "new" in result.text.lower()           # offers starting fresh
    assert len(result.text) <= 320                 # conciseness invariant (§7.1)
    outcomes = [r["payload"].get("outcome") for r in events._metric_buffer
                if r["event_name"] == "trip_focus_resolved"]
    assert "confirm_switch" in outcomes


def test_generic_plan_on_blank_trip_does_not_confirm(saga):
    # A blank DREAMING trip (no destination) has nothing to set aside, so a
    # generic PLAN proceeds to slot-fill (asks destination), no confirmation.
    with patch(_EXTRACT, return_value={}):
        result = saga.run(
            "I want to plan a trip", {}, _trip(),
            {"intent": "PLAN", "trip_directive": "unspecified"}, "", _events(),
        )
    assert result.slot_request is not None
    assert result.slot_request.slot == "destination"


def test_new_directive_acknowledges_superseded_trip(saga):
    # A fresh blank trip created by a "new" directive acknowledges the trip set
    # aside on its first prompt, then asks the destination (AC-4).
    with patch(_EXTRACT, return_value={}):
        result = saga.run(
            "actually, a new trip", {}, _trip(),
            {"intent": "PLAN", "trip_directive": "new",
             "superseded_trip_title": "Japan, autumn escape"},
            "", _events(),
        )
    assert result.slot_request.slot == "destination"
    assert "on hold" in result.text.lower()
    assert "japan" in result.text.lower()


def test_plan_intent_still_asks_missing_slot_under_unspecified(saga):
    # An established trip that is still MID slot-fill (missing budget) must keep
    # collecting on a PLAN turn — NOT confirm a switch (confirm is only for a
    # complete trip).
    with patch(_EXTRACT, return_value={}):
        result = saga.run(
            "let's plan it", {}, _trip_only_budget_missing(),
            {"intent": "PLAN", "trip_directive": "unspecified"}, "", _events(),
        )
    saga._planner.process_request.assert_not_called()
    assert result.slot_request is not None
    assert result.slot_request.slot == "budget_tier"


def test_casual_trip_question_on_full_trip_uses_companion_not_planner(saga):
    # A fully-slotted trip plus a casual TRIP question (e.g. "how's the weather?")
    # must NOT trigger the heavy PlannerAgent — the lighter companion answers, so
    # the user can drift to anything while the trip stays in focus.
    with patch(_EXTRACT, return_value={}):
        result = saga.run(
            "how's the weather in Reykjavik right now?", {},
            _trip_fully_slotted(), {"intent": "TRIP"}, "", _events(),
        )
    saga._trip_agent.process_request.assert_called_once()
    saga._planner.process_request.assert_not_called()
    assert result.slot_request is None
    assert result.text == "Some destination ideas."


def test_new_planning_fact_on_full_trip_rebuilds_via_planner(saga):
    # The user changes a planning fact on a complete trip (made_progress) → it's
    # a modification worth re-planning around, so the planner runs even on TRIP.
    with patch(_EXTRACT, return_value={"pace": "fast"}):
        result = saga.run(
            "actually make it a fast-paced trip", {},
            _trip_fully_slotted(), {"intent": "TRIP"}, "", _events(),
        )
    saga._planner.process_request.assert_called_once()
    assert result.text == "Here is your day-by-day plan."


def test_living_phase_delegates_to_trip_agent(saga):
    from datetime import date, timedelta
    today = date.today()
    t = _trip(discovery={"timeframe": {
        "start_date": str(today - timedelta(days=1)),
        "end_date": str(today + timedelta(days=3)),
    }})
    with patch(_EXTRACT, return_value={}):
        result = saga.run("what now", {}, t, {}, "", _events())
    saga._trip_agent.process_request.assert_called_once()
    assert result.text == "Some destination ideas."


# ---------------------------------------------------------------------------


# ---------------------------------------------------------------------------
# extraction → side effects
# ---------------------------------------------------------------------------

def test_extraction_produces_side_effects(saga):
    t = _trip()
    extracted = {"destinations": ["Iceland"], "pace": "slow"}
    with patch(_EXTRACT, return_value=extracted):
        result = saga.run("Iceland, slow pace", {}, t, {}, "", _events())
    kinds = [se.kind for se in result.side_effects]
    assert "destination_upsert" in kinds
    assert "trip_patch" in kinds
    patch_se = next(se for se in result.side_effects if se.kind == "trip_patch")
    assert patch_se.payload["preferences"]["pace"] == "slow"
    assert patch_se.payload["id"] == "t1"


def test_extraction_advances_missing_slot_same_turn(saga):
    # With no destination on the trip but Iceland extracted, the next missing
    # slot should be timeframe (destination now counts as filled this turn).
    t = _trip()
    with patch(_EXTRACT, return_value={"destinations": ["Iceland"]}):
        result = saga.run("Iceland", {}, t, {}, "", _events())
    assert result.slot_request.slot == "timeframe"


def test_extraction_failure_is_safe(saga):
    with patch(_EXTRACT, side_effect=RuntimeError("boom")):
        result = saga.run("plan something", {}, _trip(), {}, "", _events())
    # Degrades gracefully to asking the first slot.
    assert result.slot_request.slot == "destination"


# ---------------------------------------------------------------------------
# metrics
# ---------------------------------------------------------------------------

def test_emits_entered_and_exited_metrics(saga):
    events = _events()
    with patch(_EXTRACT, return_value={}):
        saga.run("help me plan", {}, _trip(), {}, "", events)
    names = [row["event_name"] for row in events._metric_buffer]
    assert "saga_entered" in names
    assert "slot_request_emitted" in names
    assert "saga_exited" in names


def test_should_activate_table(saga):
    assert saga.should_activate("PLAN", {}, None, {}) == (True, True)
    assert saga.should_activate("TRIP", {}, {"id": "t1"}, {}) == (True, True)
    assert saga.should_activate("TRIP", {}, None, {}) == (False, False)
    assert saga.should_activate("CHAT", {}, None, {}) == (False, False)


def test_side_effect_is_dataclass_instance(saga):
    # Guards the duck-typed apply_side_effect contract (.kind/.payload).
    with patch(_EXTRACT, return_value={"pace": "slow"}):
        result = saga.run("slow pace", {}, _trip(), {}, "", _events())
    assert all(isinstance(se, SideEffect) for se in result.side_effects)


# ---------------------------------------------------------------------------
# drift / redirect (the user can change topic instead of answering a slot)
# ---------------------------------------------------------------------------

def _trip_only_budget_missing():
    """A trip with every essential filled except budget_tier (mirrors the
    real stuck-on-budget user from Supabase)."""
    return _trip(
        destinations=[{"name": "Tokyo", "status": "considering"}],
        discovery={"timeframe": {"text": "this winter"}},
        travelers={"count": 1, "composition": "solo"},
        preferences={"pace": "medium", "structure": "full"},
    )


def test_trip_question_drifts_to_trip_agent_not_slot(saga):
    # User asks an unrelated travel question while only budget is missing.
    # The saga must ANSWER (delegate), not re-ask "What's the budget vibe?".
    with patch(_EXTRACT, return_value={}):
        result = saga.run(
            "what's the tipping etiquette in European restaurants?",
            {}, _trip_only_budget_missing(), {"intent": "TRIP"}, "", _events(),
        )
    saga._trip_agent.process_request.assert_called_once()
    assert result.slot_request is None
    assert result.text == "Some destination ideas."


def test_new_desire_drifts_to_trip_agent(saga):
    # "somewhere warm with beaches" — exploration, not a budget answer.
    with patch(_EXTRACT, return_value={}):
        result = saga.run(
            "I really want somewhere warm with great beaches, no idea where.",
            {}, _trip_only_budget_missing(), {"intent": "TRIP"}, "", _events(),
        )
    saga._trip_agent.process_request.assert_called_once()
    assert result.slot_request is None


def test_plan_intent_still_asks_missing_slot(saga):
    # An explicit PLAN turn still collects the last missing essential.
    with patch(_EXTRACT, return_value={}):
        result = saga.run(
            "let's plan it", {}, _trip_only_budget_missing(),
            {"intent": "PLAN"}, "", _events(),
        )
    assert result.slot_request is not None
    assert result.slot_request.slot == "budget_tier"


def test_trip_intent_with_new_info_continues_slot_fill(saga):
    # Even on a TRIP turn, if the user volunteered planning info we made
    # progress → keep collecting (ask the next missing slot), don't delegate.
    t = _trip(
        destinations=[{"name": "Tokyo", "status": "considering"}],
        discovery={"timeframe": {"text": "winter"}},
        travelers={"count": 1},
    )  # missing pace, structure, budget
    with patch(_EXTRACT, return_value={"pace": "slow"}):
        result = saga.run("slow pace please", {}, t, {"intent": "TRIP"}, "", _events())
    saga._trip_agent.process_request.assert_not_called()
    assert result.slot_request is not None
    assert result.slot_request.slot == "structure"


# ---------------------------------------------------------------------------
# task 43 — SlotRequest.to_wire() + deterministic selection mapper
# ---------------------------------------------------------------------------

def test_slot_request_to_wire_with_choices():
    sr = SlotRequest(
        slot="pace", prompt="What pace?",
        choices=[ChoiceOption("slow", "Slow", "slow"), ChoiceOption("skip", "Skip", "skip")],
    )
    wire = sr.to_wire()
    assert wire["slot"] == "pace"
    assert wire["allow_multi"] is False
    assert wire["choices"] == [
        {"id": "slow", "label": "Slow", "value": "slow"},
        {"id": "skip", "label": "Skip", "value": "skip"},
    ]


def test_slot_request_to_wire_free_text_has_null_choices():
    assert SlotRequest(slot="destination", prompt="Where?").to_wire()["choices"] is None


def test_selection_writes_pref_and_merges_existing():
    trip = {"id": "t1", "preferences": {"pace": "slow"}}
    se = slot_selection_to_side_effect(trip, "budget_tier", "$$")
    assert se is not None and se.kind == "trip_patch"
    # merged, not clobbered — pace survives.
    assert se.payload["preferences"] == {"pace": "slow", "budget_tier": "$$"}
    assert se.payload["id"] == "t1"


def test_selection_skip_writes_sentinel():
    se = slot_selection_to_side_effect({"id": "t1", "preferences": {}}, "pace", "skip")
    assert se.payload["preferences"]["pace"] == "skip"


def test_selection_illegal_value_returns_none():
    assert slot_selection_to_side_effect({"id": "t1"}, "pace", "zoomy") is None


def test_selection_free_text_slot_returns_none():
    # destination is parsed from text, not a tappable choice.
    assert slot_selection_to_side_effect({"id": "t1"}, "destination", "Tokyo") is None


def test_selection_no_trip_returns_none():
    assert slot_selection_to_side_effect(None, "pace", "slow") is None
    assert slot_selection_to_side_effect({}, "pace", "slow") is None
