import pytest
from unittest.mock import MagicMock, patch
from agentic_traveler.orchestrator.discovery_agent import DiscoveryAgent

@pytest.fixture
def mock_genai_client():
    with patch("agentic_traveler.orchestrator.discovery_agent.genai.Client") as mock:
        yield mock

def test_discovery_agent_init(mock_genai_client):
    agent = DiscoveryAgent(api_key="test_key")
    assert agent.client is not None

def test_discovery_agent_process_request(mock_genai_client):
    # Setup mock response
    mock_instance = mock_genai_client.return_value
    mock_model = mock_instance.models
    mock_response = MagicMock()
    mock_response.text = "1. Paris\n2. London\n3. Tokyo"
    mock_model.generate_content.return_value = mock_response
    
    agent = DiscoveryAgent(api_key="test_key")
    
    user_profile = {"user_name": "Test User", "preferences": {"budget": "High"}}
    message = "I want to go somewhere expensive"
    
    response = agent.process_request(user_profile, message)
    
    assert response["action"] == "DISCOVERY_RESULTS"
    assert "Paris" in response["text"]
    
    # Verify call arguments
    args, kwargs = mock_model.generate_content.call_args
    assert kwargs['model'] == "gemini-3.1-pro"
    assert "Test User" in kwargs['contents']
    assert "expensive" in kwargs['contents']
