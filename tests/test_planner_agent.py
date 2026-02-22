import pytest
from unittest.mock import MagicMock
from agentic_traveler.orchestrator.planner_agent import PlannerAgent


@pytest.fixture
def mock_client():
    return MagicMock()


def test_planner_agent_init(mock_client):
    agent = PlannerAgent(client=mock_client)
    assert agent.client is not None
    assert agent.model_name == "gemini-3-flash-preview"


def test_planner_agent_process_request(mock_client):
    mock_response = MagicMock()
    mock_response.text = "Day 1: Arrival\nDay 2: Sightseeing"
    mock_client.models.generate_content.return_value = mock_response

    agent = PlannerAgent(client=mock_client)

    user_profile = {"user_name": "Test User", "user_profile": {"pace": "Relaxed"}}
    message = "Plan a 3 day trip to Rome"

    response = agent.process_request(user_profile, message)

    assert response["action"] == "PLANNER_RESULTS"
    assert "Day 1" in response["text"]

    args, kwargs = mock_client.models.generate_content.call_args
    assert kwargs['model'] == "gemini-3-flash-preview"
    assert "Test User" in kwargs['contents']
    assert "Rome" in kwargs['contents']
