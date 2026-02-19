import pytest
from unittest.mock import MagicMock, patch
from agentic_traveler.orchestrator.agent import OrchestratorAgent
from agentic_traveler.tools.firestore_user import FirestoreUserTool

@pytest.fixture
def mock_user_tool():
    tool = MagicMock(spec=FirestoreUserTool)
    return tool

def test_new_user_flow(mock_user_tool):
    # Setup: User not found
    mock_user_tool.get_user_by_telegram_id.return_value = None
    
    agent = OrchestratorAgent(firestore_user_tool=mock_user_tool)
    response = agent.process_request("123", "Hello")
    
    assert response["action"] == "ONBOARDING_REQUIRED"
    assert "tally.so" in response["text"]

def test_existing_user_chat(mock_user_tool):
    # Setup: User found
    mock_user_tool.get_user_by_telegram_id.return_value = {"user_name": "Alice"}
    
    agent = OrchestratorAgent(firestore_user_tool=mock_user_tool)
    response = agent.process_request("123", "Hello")
    
    assert response["action"] == "CHAT_REPLY"
    assert "Hello Alice" in response["text"]

def test_new_trip_intent(mock_user_tool):
    mock_user_tool.get_user_by_telegram_id.return_value = {"user_name": "Bob"}
    
    with patch("agentic_traveler.orchestrator.agent.DiscoveryAgent") as MockDiscovery:
        mock_discovery_instance = MockDiscovery.return_value
        mock_discovery_instance.process_request.return_value = {"action": "DISCOVERY_RESULTS", "text": "Tokyo"}
        
        agent = OrchestratorAgent(firestore_user_tool=mock_user_tool)
        response = agent.process_request("123", "I want to plan a trip to Japan")
        
        assert response["action"] == "DISCOVERY_RESULTS"
        mock_discovery_instance.process_request.assert_called_once()

def test_in_trip_intent(mock_user_tool):
    mock_user_tool.get_user_by_telegram_id.return_value = {"user_name": "Bob"}
    
    agent = OrchestratorAgent(firestore_user_tool=mock_user_tool)
    response = agent.process_request("123", "I am tired and hungry here")
    
    assert response["action"] == "COMPANION_TRIGGERED"
