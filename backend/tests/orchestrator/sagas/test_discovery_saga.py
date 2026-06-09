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
