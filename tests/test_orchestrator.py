import pytest
from unittest.mock import MagicMock, patch
from agentic_traveler.orchestrator.agent import OrchestratorAgent
from agentic_traveler.tools.firestore_user import FirestoreUserTool


@pytest.fixture
def mock_user_tool():
    tool = MagicMock(spec=FirestoreUserTool)
    return tool


@pytest.fixture
def patched_deps():
    """Patch all downstream dependencies of OrchestratorAgent."""
    with patch("agentic_traveler.orchestrator.agent.IntentClassifier") as clf, \
         patch("agentic_traveler.orchestrator.agent.SafetyFilter") as sf, \
         patch("agentic_traveler.orchestrator.agent.DiscoveryAgent") as disc, \
         patch("agentic_traveler.orchestrator.agent.PlannerAgent") as plan, \
         patch("agentic_traveler.orchestrator.agent.CompanionAgent") as comp:
        # Default: safety filter passes text through unchanged
        sf.return_value.filter.side_effect = lambda t: t
        yield {
            "classifier": clf,
            "safety": sf,
            "discovery": disc,
            "planner": plan,
            "companion": comp,
        }


def test_new_user_flow(mock_user_tool, patched_deps):
    mock_user_tool.get_user_by_telegram_id.return_value = None
    agent = OrchestratorAgent(firestore_user_tool=mock_user_tool)
    response = agent.process_request("123", "Hello")
    assert response["action"] == "ONBOARDING_REQUIRED"
    assert "tally.so" in response["text"]


def test_existing_user_chat(mock_user_tool, patched_deps):
    mock_user_tool.get_user_by_telegram_id.return_value = {"user_name": "Alice"}
    patched_deps["classifier"].return_value.classify.return_value = "CHAT"
    agent = OrchestratorAgent(firestore_user_tool=mock_user_tool)
    response = agent.process_request("123", "Hello")
    assert response["action"] == "CHAT_REPLY"
    assert "Hello Alice" in response["text"]


def test_new_trip_intent(mock_user_tool, patched_deps):
    mock_user_tool.get_user_by_telegram_id.return_value = {"user_name": "Bob"}
    patched_deps["classifier"].return_value.classify.return_value = "NEW_TRIP"
    patched_deps["discovery"].return_value.process_request.return_value = {
        "action": "DISCOVERY_RESULTS", "text": "Tokyo"
    }
    agent = OrchestratorAgent(firestore_user_tool=mock_user_tool)
    response = agent.process_request("123", "I want to explore Japan")
    assert response["action"] == "DISCOVERY_RESULTS"
    patched_deps["discovery"].return_value.process_request.assert_called_once()


def test_planning_intent(mock_user_tool, patched_deps):
    mock_user_tool.get_user_by_telegram_id.return_value = {"user_name": "Bob"}
    patched_deps["classifier"].return_value.classify.return_value = "PLANNING"
    patched_deps["planner"].return_value.process_request.return_value = {
        "action": "PLANNER_RESULTS", "text": "Itinerary"
    }
    agent = OrchestratorAgent(firestore_user_tool=mock_user_tool)
    response = agent.process_request("123", "Build a schedule for Rome")
    assert response["action"] == "PLANNER_RESULTS"
    patched_deps["planner"].return_value.process_request.assert_called_once()


def test_in_trip_intent(mock_user_tool, patched_deps):
    mock_user_tool.get_user_by_telegram_id.return_value = {"user_name": "Bob"}
    patched_deps["classifier"].return_value.classify.return_value = "IN_TRIP"
    patched_deps["companion"].return_value.process_request.return_value = {
        "action": "COMPANION_RESULTS", "text": "Café nearby"
    }
    agent = OrchestratorAgent(firestore_user_tool=mock_user_tool)
    response = agent.process_request("123", "I am tired and hungry")
    assert response["action"] == "COMPANION_RESULTS"
    patched_deps["companion"].return_value.process_request.assert_called_once()


def test_safety_filter_is_applied(mock_user_tool, patched_deps):
    """Verifies the safety filter runs on every response."""
    mock_user_tool.get_user_by_telegram_id.return_value = {"user_name": "Eve"}
    patched_deps["classifier"].return_value.classify.return_value = "CHAT"
    patched_deps["safety"].return_value.filter.side_effect = None
    patched_deps["safety"].return_value.filter.return_value = "FILTERED"
    agent = OrchestratorAgent(firestore_user_tool=mock_user_tool)
    response = agent.process_request("123", "Hey")
    assert response["text"] == "FILTERED"
    patched_deps["safety"].return_value.filter.assert_called_once()
