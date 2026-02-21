import pytest
from unittest.mock import MagicMock, patch
from agentic_traveler.orchestrator.companion_agent import CompanionAgent


@pytest.fixture
def mock_genai_client():
    with patch("agentic_traveler.orchestrator.companion_agent.genai.Client") as mock:
        yield mock


def test_companion_agent_init(mock_genai_client):
    agent = CompanionAgent(api_key="test_key")
    assert agent.client is not None
    assert agent.model_name == "gemini-3.1-pro"


def test_companion_agent_process_request(mock_genai_client):
    # Setup mock response
    mock_instance = mock_genai_client.return_value
    mock_model = mock_instance.models
    mock_response = MagicMock()
    mock_response.text = (
        "1. Café nearby\n2. Park stroll\n3. Quick nap at the hotel"
    )
    mock_model.generate_content.return_value = mock_response

    agent = CompanionAgent(api_key="test_key")

    user_profile = {
        "user_name": "Alice",
        "preferences": {"vibes": "nature", "avoidances": "crowds"},
    }
    message = "I'm tired and hungry here"

    response = agent.process_request(user_profile, message)

    assert response["action"] == "COMPANION_RESULTS"
    assert "Café" in response["text"]

    # Verify call arguments
    args, kwargs = mock_model.generate_content.call_args
    assert kwargs["model"] == "gemini-3.1-pro"
    assert "Alice" in kwargs["contents"]
    assert "tired" in kwargs["contents"]


def test_companion_agent_missing_api_key():
    """When no API key is provided the agent should return an error."""
    with patch.dict("os.environ", {}, clear=True):
        with patch(
            "agentic_traveler.orchestrator.companion_agent.genai.Client"
        ) as mock_client:
            # Simulate no api_key → client is None
            agent = CompanionAgent(api_key=None)
            agent.client = None  # force None for this test

            response = agent.process_request(
                {"user_name": "Bob"}, "I'm bored"
            )
            assert response["action"] == "ERROR"
