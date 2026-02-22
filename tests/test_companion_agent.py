import pytest
from unittest.mock import MagicMock
from agentic_traveler.orchestrator.companion_agent import CompanionAgent


@pytest.fixture
def mock_client():
    return MagicMock()


def test_companion_agent_init(mock_client):
    agent = CompanionAgent(client=mock_client)
    assert agent.client is not None
    assert agent.model_name == "gemini-3-flash-preview"


def test_companion_agent_process_request(mock_client):
    mock_response = MagicMock()
    mock_response.text = "1. Café nearby\n2. Park stroll\n3. Quick nap at the hotel"
    mock_client.models.generate_content.return_value = mock_response

    agent = CompanionAgent(client=mock_client)

    user_profile = {
        "user_name": "Alice",
        "user_profile": {"vibes": "nature", "avoidances": "crowds"},
    }
    message = "I'm tired and hungry here"

    response = agent.process_request(user_profile, message)

    assert response["action"] == "COMPANION_RESULTS"
    assert "Café" in response["text"]

    args, kwargs = mock_client.models.generate_content.call_args
    assert kwargs["model"] == "gemini-3-flash-preview"
    assert "Alice" in kwargs["contents"]
    assert "tired" in kwargs["contents"]


def test_companion_agent_missing_client():
    """When no client is provided the agent should return an error."""
    agent = CompanionAgent(client=None)
    response = agent.process_request({"user_name": "Bob"}, "I'm bored")
    assert response["action"] == "ERROR"
