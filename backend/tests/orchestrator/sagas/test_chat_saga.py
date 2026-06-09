"""ChatSaga unit tests."""

from unittest.mock import ANY, MagicMock, patch
import pytest

from agentic_traveler.orchestrator.event_emitter import EventEmitter
from agentic_traveler.orchestrator.sagas.chat import ChatSaga

@pytest.fixture
def saga():
    with patch("agentic_traveler.orchestrator.sagas.chat.ChatAgent"):
        s = ChatSaga(client=MagicMock())
    s._chat_agent = MagicMock()
    s._chat_agent.process_request.return_value = {
        "text": "Hello, how can I help?",
        "_raw_response": None, "_latency_ms": 1.0, "_search_responses": []
    }
    return s

def _events():
    return EventEmitter(user_id="u1", trip_id="t1")

def test_should_activate_table(saga):
    assert saga.should_activate("CHAT", {}, None, {}) == (True, True)
    assert saga.should_activate("PLAN", {}, None, {}) == (False, False)
    assert saga.should_activate("OFF_TOPIC", {}, None, {}) == (False, False)

def test_chat_saga_delegates_to_chat_agent(saga):
    events = _events()
    user_doc = {"user_profile": {"profile_data": {}}}
    
    result = saga.run("hi", user_doc, None, {}, "", events)
    
    saga._chat_agent.process_request.assert_called_once_with(
        user_doc=user_doc,
        message="hi",
        conversation_context="",
        current_time="",
        preference_raw=None,
        events=ANY,
    )
    assert result.text == "Hello, how can I help?"
    
    names = [row["event_name"] for row in events._metric_buffer]
    assert "saga_entered" in names
    assert "saga_exited" in names

def test_chat_saga_handles_delegate_error(saga):
    events = _events()
    saga._chat_agent.process_request.side_effect = RuntimeError("boom")
    
    result = saga.run("hi", {}, None, {}, "", events)
    
    assert "Sorry" in result.text
    names = [row["event_name"] for row in events._metric_buffer]
    assert "error_raised" in names
