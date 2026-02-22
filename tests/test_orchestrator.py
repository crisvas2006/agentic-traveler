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
         patch("agentic_traveler.orchestrator.agent.CompanionAgent") as comp, \
         patch("agentic_traveler.orchestrator.agent.ChatAgent") as chat, \
         patch("agentic_traveler.orchestrator.agent.ConversationManager") as conv, \
         patch("agentic_traveler.orchestrator.agent.PreferenceLearner") as pref:
        # Default: safety filter passes text through unchanged
        sf.return_value.filter.side_effect = lambda t: t
        # Default: conversation context is empty
        conv.return_value.build_context_block.return_value = ""
        # Default: classifier returns (intent, False)
        clf.return_value.classify.return_value = ("CHAT", False)
        yield {
            "classifier": clf,
            "safety": sf,
            "discovery": disc,
            "planner": plan,
            "companion": comp,
            "chat": chat,
            "conversation": conv,
            "preference": pref,
        }


def test_new_user_flow(mock_user_tool, patched_deps):
    mock_user_tool.get_user_with_ref.return_value = (None, None)
    agent = OrchestratorAgent(firestore_user_tool=mock_user_tool)
    response = agent.process_request("123", "Hello")
    assert response["action"] == "ONBOARDING_REQUIRED"
    assert "tally.so" in response["text"]


def test_existing_user_chat(mock_user_tool, patched_deps):
    doc_ref = MagicMock()
    mock_user_tool.get_user_with_ref.return_value = ({"user_name": "Alice"}, doc_ref)
    patched_deps["classifier"].return_value.classify.return_value = ("CHAT", False)
    patched_deps["chat"].return_value.process_request.return_value = {
        "action": "CHAT_REPLY", "text": "Hello Alice!"
    }
    agent = OrchestratorAgent(firestore_user_tool=mock_user_tool)
    response = agent.process_request("123", "Hello")
    assert response["action"] == "CHAT_REPLY"
    patched_deps["chat"].return_value.process_request.assert_called_once()


def test_new_trip_intent(mock_user_tool, patched_deps):
    doc_ref = MagicMock()
    mock_user_tool.get_user_with_ref.return_value = ({"user_name": "Bob"}, doc_ref)
    patched_deps["classifier"].return_value.classify.return_value = ("NEW_TRIP", False)
    patched_deps["discovery"].return_value.process_request.return_value = {
        "action": "DISCOVERY_RESULTS", "text": "Tokyo"
    }
    agent = OrchestratorAgent(firestore_user_tool=mock_user_tool)
    response = agent.process_request("123", "I want to explore Japan")
    assert response["action"] == "DISCOVERY_RESULTS"
    patched_deps["discovery"].return_value.process_request.assert_called_once()


def test_planning_intent(mock_user_tool, patched_deps):
    doc_ref = MagicMock()
    mock_user_tool.get_user_with_ref.return_value = ({"user_name": "Bob"}, doc_ref)
    patched_deps["classifier"].return_value.classify.return_value = ("PLANNING", False)
    patched_deps["planner"].return_value.process_request.return_value = {
        "action": "PLANNER_RESULTS", "text": "Itinerary"
    }
    agent = OrchestratorAgent(firestore_user_tool=mock_user_tool)
    response = agent.process_request("123", "Build a schedule for Rome")
    assert response["action"] == "PLANNER_RESULTS"
    patched_deps["planner"].return_value.process_request.assert_called_once()


def test_in_trip_intent(mock_user_tool, patched_deps):
    doc_ref = MagicMock()
    mock_user_tool.get_user_with_ref.return_value = ({"user_name": "Bob"}, doc_ref)
    patched_deps["classifier"].return_value.classify.return_value = ("IN_TRIP", False)
    patched_deps["companion"].return_value.process_request.return_value = {
        "action": "COMPANION_RESULTS", "text": "Café nearby"
    }
    agent = OrchestratorAgent(firestore_user_tool=mock_user_tool)
    response = agent.process_request("123", "I am tired and hungry")
    assert response["action"] == "COMPANION_RESULTS"
    patched_deps["companion"].return_value.process_request.assert_called_once()


def test_safety_filter_is_applied(mock_user_tool, patched_deps):
    """Verifies the safety filter runs on every response."""
    doc_ref = MagicMock()
    mock_user_tool.get_user_with_ref.return_value = ({"user_name": "Eve"}, doc_ref)
    patched_deps["classifier"].return_value.classify.return_value = ("CHAT", False)
    patched_deps["chat"].return_value.process_request.return_value = {
        "action": "CHAT_REPLY", "text": "Hi Eve!"
    }
    patched_deps["safety"].return_value.filter.side_effect = None
    patched_deps["safety"].return_value.filter.return_value = "FILTERED"
    agent = OrchestratorAgent(firestore_user_tool=mock_user_tool)
    response = agent.process_request("123", "Hey")
    assert response["text"] == "FILTERED"
    patched_deps["safety"].return_value.filter.assert_called_once()


def test_conversation_saved_after_response(mock_user_tool, patched_deps):
    """Verifies conversation history is saved after each exchange."""
    doc_ref = MagicMock()
    mock_user_tool.get_user_with_ref.return_value = ({"user_name": "Eve"}, doc_ref)
    patched_deps["chat"].return_value.process_request.return_value = {
        "action": "CHAT_REPLY", "text": "Hello!"
    }
    agent = OrchestratorAgent(firestore_user_tool=mock_user_tool)
    agent.process_request("123", "Hi")
    patched_deps["conversation"].return_value.append_and_save.assert_called_once()


def test_preference_extraction_triggered(mock_user_tool, patched_deps):
    """When classifier flags PREF, PreferenceLearner is called."""
    doc_ref = MagicMock()
    mock_user_tool.get_user_with_ref.return_value = ({"user_name": "Eve"}, doc_ref)
    patched_deps["classifier"].return_value.classify.return_value = ("CHAT", True)
    patched_deps["chat"].return_value.process_request.return_value = {
        "action": "CHAT_REPLY", "text": "Got it!"
    }
    agent = OrchestratorAgent(firestore_user_tool=mock_user_tool)
    agent.process_request("123", "I hate crowded places")
    patched_deps["preference"].return_value.extract_and_save.assert_called_once()


def test_preference_extraction_not_triggered(mock_user_tool, patched_deps):
    """When classifier does NOT flag PREF, PreferenceLearner is NOT called."""
    doc_ref = MagicMock()
    mock_user_tool.get_user_with_ref.return_value = ({"user_name": "Eve"}, doc_ref)
    patched_deps["classifier"].return_value.classify.return_value = ("CHAT", False)
    patched_deps["chat"].return_value.process_request.return_value = {
        "action": "CHAT_REPLY", "text": "Hello!"
    }
    agent = OrchestratorAgent(firestore_user_tool=mock_user_tool)
    agent.process_request("123", "Hello")
    patched_deps["preference"].return_value.extract_and_save.assert_not_called()
