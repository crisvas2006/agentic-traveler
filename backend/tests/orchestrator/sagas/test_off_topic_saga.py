"""OffTopicSaga unit tests."""

from unittest.mock import MagicMock
import pytest

from agentic_traveler.orchestrator.event_emitter import EventEmitter
from agentic_traveler.orchestrator.sagas.off_topic import OffTopicSaga, _REDIRECT

@pytest.fixture
def saga():
    s = OffTopicSaga(client=MagicMock())
    return s

def _events():
    return EventEmitter(user_id="u1", trip_id="t1")

def test_should_activate_table(saga):
    assert saga.should_activate("OFF_TOPIC", {}, None, {}) == (True, True)
    assert saga.should_activate("PLAN", {}, None, {}) == (False, False)

def test_off_topic_saga_returns_redirect(saga):
    events = _events()
    
    result = saga.run("write me a python script", {}, None, {}, "", events)
    
    assert result.text == _REDIRECT
    
    names = [row["event_name"] for row in events._metric_buffer]
    assert "saga_entered" in names
    assert "saga_exited" in names

def test_off_topic_saga_returns_router_response(saga):
    events = _events()
    
    result = saga.run("hi", {}, None, {"router_response": "I see you like python"}, "", events)
    
    assert result.text == "I see you like python"
