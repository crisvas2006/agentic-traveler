import pytest
from unittest.mock import MagicMock, patch
from agentic_traveler.travel_agent import TravelAgent

@pytest.fixture
def mock_genai_client():
    with patch('agentic_traveler.travel_agent.genai.Client') as mock:
        yield mock

def test_init_no_api_key(monkeypatch):
    monkeypatch.delenv("GOOGLE_API_KEY", raising=False)
    with pytest.raises(ValueError, match="API key must be provided"):
        TravelAgent(api_key=None)

def test_init_with_api_key(mock_genai_client):
    agent = TravelAgent(api_key="test_key")
    assert agent.api_key == "test_key"
    mock_genai_client.assert_called_once_with(api_key="test_key")

def test_generate_travel_idea(mock_genai_client):
    # Setup mock response
    mock_response = MagicMock()
    mock_response.text = "Visit Paris!"
    
    mock_client_instance = mock_genai_client.return_value
    mock_client_instance.models.generate_content.return_value = mock_response

    agent = TravelAgent(api_key="test_key")
    preferences = {
        "budget": "high",
        "climate": "temperate",
        "activity": "culture",
        "duration": "1 week"
    }
    
    idea = agent.generate_travel_idea(preferences)
    
    assert idea == "Visit Paris!"
    mock_client_instance.models.generate_content.assert_called_once()
    
    # Verify prompt contains preferences
    call_args = mock_client_instance.models.generate_content.call_args
    assert "high" in call_args.kwargs['contents']
    assert "temperate" in call_args.kwargs['contents']

def test_generate_travel_idea_error(mock_genai_client):
    mock_client_instance = mock_genai_client.return_value
    mock_client_instance.models.generate_content.side_effect = Exception("API Error")

    agent = TravelAgent(api_key="test_key")
    idea = agent.generate_travel_idea({})
    
    assert "Error generating travel idea" in idea
