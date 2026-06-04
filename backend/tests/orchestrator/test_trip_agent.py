import pytest
from unittest.mock import MagicMock
from agentic_traveler.orchestrator.trip_agent import TripAgent

@pytest.fixture
def mock_client():
    return MagicMock()

def test_trip_agent_init(mock_client):
    agent = TripAgent(client=mock_client)
    assert agent._client == mock_client

def test_trip_agent_process_request(mock_client):
    mock_response = MagicMock()
    mock_response.text = "1. Paris\n2. London"
    mock_client.models.generate_content.return_value = mock_response

    agent = TripAgent(client=mock_client)
    user_profile = {"user_name": "Test User", "user_profile": {"budget": "High"}}
    
    response = agent.process_request(
        user_doc=user_profile,
        message="Suggest destinations",
        conversation_context="context",
        current_time="time",
    )

    assert response["action"] == "TRIP_RESULTS"
    assert "Paris" in response["text"]

    kwargs = mock_client.models.generate_content.call_args.kwargs
    assert kwargs['model'] == "gemini-3.5-flash"
    assert "Test User" in kwargs['contents']
    assert "Suggest destinations" in kwargs['contents']
    config = kwargs.get("config")
    assert config is not None
    from agentic_traveler.orchestrator.utils import check_weather
    assert check_weather in config.tools

def test_trip_agent_error(mock_client):
    mock_client.models.generate_content.side_effect = Exception("LLM failure")
    agent = TripAgent(client=mock_client)
    
    response = agent.process_request(
        user_doc={"user_name": "Alice"},
        message="Suggest destinations",
        conversation_context="context",
        current_time="time",
    )
    assert response["action"] == "ERROR"
    assert "snag" in response["text"]
