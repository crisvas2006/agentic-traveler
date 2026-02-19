import pytest
from unittest.mock import MagicMock, patch
from agentic_traveler.orchestrator.planner_agent import PlannerAgent

@pytest.fixture
def mock_genai_client():
    with patch("agentic_traveler.orchestrator.planner_agent.genai.Client") as mock:
        yield mock

def test_planner_agent_init(mock_genai_client):
    agent = PlannerAgent(api_key="test_key")
    assert agent.client is not None
    assert agent.model_name == "gemini-3.1-pro"

def test_planner_agent_process_request(mock_genai_client):
    # Setup mock response
    mock_instance = mock_genai_client.return_value
    mock_model = mock_instance.models
    mock_response = MagicMock()
    mock_response.text = "Day 1: Arrival\nDay 2: Sightseeing"
    mock_model.generate_content.return_value = mock_response
    
    agent = PlannerAgent(api_key="test_key")
    
    user_profile = {"user_name": "Test User", "preferences": {"pace": "Relaxed"}}
    message = "Plan a 3 day trip to Rome"
    
    response = agent.process_request(user_profile, message)
    
    assert response["action"] == "PLANNER_RESULTS"
    assert "Day 1" in response["text"]
    
    # Verify call arguments
    args, kwargs = mock_model.generate_content.call_args
    assert kwargs['model'] == "gemini-3.1-pro"
    assert "Test User" in kwargs['contents']
    assert "Rome" in kwargs['contents']
