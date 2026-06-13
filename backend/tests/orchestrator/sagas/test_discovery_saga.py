"""DiscoverySaga unit tests."""

from unittest.mock import MagicMock, patch
import pytest

from agentic_traveler.orchestrator.event_emitter import EventEmitter
from agentic_traveler.orchestrator.sagas.discovery import DiscoverySaga

@pytest.fixture
def saga():
    with patch("agentic_traveler.orchestrator.sagas.discovery.TripAgent"):
        s = DiscoverySaga(client=MagicMock())
    s._trip_agent = MagicMock()
    s._trip_agent.process_request.return_value = {
        "text": "How about Japan?",
        "_raw_response": None, "_latency_ms": 1.0, "_search_responses": []
    }
    return s

def _events():
    return EventEmitter(user_id="u1", trip_id=None)

def test_should_activate_table(saga):
    assert saga.should_activate("TRIP", {}, None, {}) == (True, True)
    assert saga.should_activate("TRIP", {}, {"id": "t1"}, {}) == (False, False)
    assert saga.should_activate("PLAN", {}, None, {}) == (False, False)

def test_discovery_saga_delegates_to_trip_agent(saga):
    events = _events()
    user_doc = {"user_profile": {"profile_data": {}}}
    
    state = {"entities": {"destinations": ["Japan"]}}
    result = saga.run("I want to go to Japan", user_doc, {"id": "t1"}, state, "", events)
    
    saga._trip_agent.process_request.assert_called_once()
    assert result.text == "How about Japan?"
    
    kinds = [se.kind for se in result.side_effects]
    assert "destination_upsert" in kinds
    
    names = [row["event_name"] for row in events._metric_buffer]
    assert "saga_entered" in names
    assert "saga_exited" in names

def test_discovery_saga_handles_delegate_error(saga):
    events = _events()
    saga._trip_agent.process_request.side_effect = RuntimeError("boom")

    result = saga.run("hi", {}, None, {}, "", events)

    assert "Sorry" in result.text
    names = [row["event_name"] for row in events._metric_buffer]
    assert "error_raised" in names


# ---------------------------------------------------------------------------
# task 52 — relaxed, consented trip creation
# ---------------------------------------------------------------------------

def test_casual_question_creates_nothing_and_answers(saga):
    """AC-13: a casual question with no trip → TripAgent answer, no trip, no
    side effects, no confirmation chip."""
    events = _events()
    user_doc = {"user_profile": {"profile_data": {}}}
    state = {"entities": {"destinations": ["Rome"]}}

    result = saga.run("what is a trip in Rome like?", user_doc, None, state, "", events)

    saga._trip_agent.process_request.assert_called_once()
    assert result.text == "How about Japan?"
    assert result.side_effects == []
    assert result.slot_request is None


def test_soft_cue_confirms_before_creating(saga):
    """AC-14: a soft desire-to-travel cue with a named place → a ≤200-char
    confirmation, NO TripAgent call, NO side effects, NO trip created."""
    events = _events()
    user_doc = {"user_profile": {"profile_data": {}}}
    state = {"entities": {"destinations": ["Rome"]}}

    result = saga.run("I'm thinking of going to Rome someday", user_doc, None, state, "", events)

    saga._trip_agent.process_request.assert_not_called()
    assert result.side_effects == []
    assert "Rome" in result.text
    assert len(result.text) <= 200
    assert result.slot_request is not None
    assert result.slot_request.slot == "trip_create"


def test_soft_cue_without_destination_just_answers(saga):
    """A soft cue with no named place can't form a 'start a trip for X?' prompt →
    fall through to a normal conversational answer (no nag)."""
    events = _events()
    user_doc = {"user_profile": {"profile_data": {}}}
    state = {"entities": {"destinations": []}}

    result = saga.run("I want to go to somewhere warm", user_doc, None, state, "", events)

    saga._trip_agent.process_request.assert_called_once()
    assert result.slot_request is None


def test_go_signal_with_existing_trip_delegates_and_stages(saga):
    """An explicit go-signal arrives with a trip already created by the
    orchestrator → delegate to TripAgent and stage the destination (no confirm)."""
    events = _events()
    user_doc = {"user_profile": {"profile_data": {}}}
    state = {"entities": {"destinations": ["Rome"]}}

    result = saga.run("let's plan a trip to Rome", user_doc, {"id": "t1"}, state, "", events)

    saga._trip_agent.process_request.assert_called_once()
    kinds = [se.kind for se in result.side_effects]
    assert "destination_upsert" in kinds


def test_has_go_signal_detects_explicit_phrases():
    from agentic_traveler.orchestrator.sagas.discovery import has_go_signal
    assert has_go_signal("let's plan a trip to Rome")
    assert has_go_signal("Plan me a 5-day Tokyo itinerary")
    assert not has_go_signal("what is Rome like?")
    assert not has_go_signal("I'm thinking of going to Rome")
