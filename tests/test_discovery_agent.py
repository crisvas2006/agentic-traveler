import pytest
from unittest.mock import MagicMock, patch
from agentic_traveler.orchestrator.discovery_agent import DiscoveryAgent


@pytest.fixture
def mock_client():
    return MagicMock()


def test_discovery_agent_init(mock_client):
    agent = DiscoveryAgent(client=mock_client)
    assert agent.client is not None


def test_discovery_agent_process_request(mock_client):
    mock_response = MagicMock()
    mock_response.text = "1. Paris\n2. London\n3. Tokyo"
    mock_client.models.generate_content.return_value = mock_response

    agent = DiscoveryAgent(client=mock_client)

    user_profile = {"user_name": "Test User", "user_profile": {"budget": "High"}}
    message = "I want to go somewhere expensive"

    response = agent.process_request(user_profile, message)

    assert response["action"] == "DISCOVERY_RESULTS"
    assert "Paris" in response["text"]

    # Verify call arguments
    args, kwargs = mock_client.models.generate_content.call_args
    assert kwargs['model'] == "gemini-3-flash-preview"
    assert "Test User" in kwargs['contents']
    assert "expensive" in kwargs['contents']
