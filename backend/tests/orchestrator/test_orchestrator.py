import pytest
from unittest.mock import MagicMock, patch
from agentic_traveler.orchestrator.agent import OrchestratorAgent
from agentic_traveler.tools.user_repo import UserRepository

@pytest.fixture
def mock_user_repo():
    return MagicMock(spec=UserRepository)

@pytest.fixture
def patched_deps():
    with patch("agentic_traveler.orchestrator.agent.RouterAgent") as mock_router, \
         patch("agentic_traveler.orchestrator.agent.ChatAgent") as mock_chat, \
         patch("agentic_traveler.orchestrator.agent.TripAgent") as mock_trip, \
         patch("agentic_traveler.orchestrator.agent.PlannerAgent") as mock_planner, \
         patch("agentic_traveler.orchestrator.agent.ConversationManager") as mock_conv, \
         patch("agentic_traveler.orchestrator.agent.credit_manager") as mock_credits, \
         patch("agentic_traveler.orchestrator.agent.off_topic_guard") as mock_guard, \
         patch("agentic_traveler.orchestrator.agent.get_client") as mock_get_client:
        
        mock_client = MagicMock()
        mock_get_client.return_value = mock_client
        mock_credits.has_credits.return_value = True
        mock_guard.is_restricted.return_value = None
        mock_conv.return_value.build_context_block.return_value = "Mock history"
        
        yield {
            "router": mock_router,
            "chat": mock_chat,
            "trip": mock_trip,
            "planner": mock_planner,
            "conv": mock_conv,
            "credits": mock_credits,
            "guard": mock_guard,
            "client": mock_client,
        }

def test_new_user_onboarding(mock_user_repo, patched_deps):
    """Unknown Telegram ID → onboarding link."""
    mock_user_repo.get_user_with_ref.return_value = (None, None)
    agent = OrchestratorAgent(user_repo=mock_user_repo)
    response = agent.process_request("unknown_id", "Hello")
    assert response["action"] == "ONBOARDING_REQUIRED"
    assert "tally.so" in response["text"]

def test_credit_exhausted(mock_user_repo, patched_deps):
    """If user has no credits, return credits exhausted message."""
    mock_user_repo.get_user_with_ref.return_value = ({"user_name": "Alice"}, "user-id-123")
    patched_deps["credits"].has_credits.return_value = False
    
    agent = OrchestratorAgent(user_repo=mock_user_repo)
    response = agent.process_request("123", "Hello")
    assert response["action"] == "NO_CREDITS"
    assert response["text"] == patched_deps["credits"].CREDITS_EXHAUSTED_MSG

def test_user_restricted(mock_user_repo, patched_deps):
    """If user is restricted, return off-topic restriction message."""
    mock_user_repo.get_user_with_ref.return_value = ({"user_name": "Alice"}, "user-id-123")
    patched_deps["guard"].is_restricted.return_value = "You are restricted"
    
    agent = OrchestratorAgent(user_repo=mock_user_repo)
    response = agent.process_request("123", "Hello")
    assert response["action"] == "RESTRICTED"
    assert "restricted" in response["text"].lower()

def test_off_topic_intent(mock_user_repo, patched_deps):
    """If router returns OFF_TOPIC, record off-topic and return redirect text."""
    mock_user_repo.get_user_with_ref.return_value = ({"user_name": "Alice"}, "user-id-123")
    patched_deps["router"].return_value.classify.return_value = {
        "intent": "OFF_TOPIC",
        "response": "Please ask travel questions",
        "raw_response": MagicMock(),
        "latency_ms": 100
    }
    patched_deps["guard"].record_off_topic.return_value = {"restricted": False}
    
    agent = OrchestratorAgent(user_repo=mock_user_repo)
    response = agent.process_request("123", "Help with math")
    
    assert response["action"] == "RESPONSE"
    assert "travel" in response["text"]
    patched_deps["guard"].record_off_topic.assert_called_once()

def test_dispatch_to_trip_agent(mock_user_repo, patched_deps):
    """TRIP intent should dispatch to TripAgent."""
    mock_user_repo.get_user_with_ref.return_value = ({"user_name": "Alice"}, "user-id-123")
    patched_deps["router"].return_value.classify.return_value = {
        "intent": "TRIP",
        "preference_updated": None,
        "raw_response": MagicMock(),
        "latency_ms": 100
    }
    mock_trip_instance = patched_deps["trip"].return_value
    mock_trip_instance.process_request.return_value = {
        "text": "Check out Paris!",
        "action": "TRIP_RESULTS",
        "_raw_response": MagicMock(),
        "_latency_ms": 200
    }
    
    agent = OrchestratorAgent(user_repo=mock_user_repo)
    response = agent.process_request("123", "Where should I go?")
    
    assert response["action"] == "RESPONSE"
    assert "Paris" in response["text"]
    mock_trip_instance.process_request.assert_called_once()

def test_dispatch_to_planner_agent(mock_user_repo, patched_deps):
    """PLAN intent should dispatch to PlannerAgent."""
    mock_user_repo.get_user_with_ref.return_value = ({"user_name": "Alice"}, "user-id-123")
    patched_deps["router"].return_value.classify.return_value = {
        "intent": "PLAN",
        "preference_updated": None,
        "raw_response": MagicMock(),
        "latency_ms": 100
    }
    mock_planner_instance = patched_deps["planner"].return_value
    mock_planner_instance.process_request.return_value = {
        "text": "Day 1: Rome",
        "action": "PLANNER_RESULTS",
        "_raw_response": MagicMock(),
        "_latency_ms": 200
    }
    
    agent = OrchestratorAgent(user_repo=mock_user_repo)
    response = agent.process_request("123", "Plan me 3 days in Rome")
    
    assert response["action"] == "RESPONSE"
    assert "Rome" in response["text"]
    mock_planner_instance.process_request.assert_called_once()
