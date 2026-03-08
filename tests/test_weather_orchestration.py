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
    with patch("agentic_traveler.orchestrator.agent.DiscoveryAgent"), \
         patch("agentic_traveler.orchestrator.agent.PlannerAgent"), \
         patch("agentic_traveler.orchestrator.agent.CompanionAgent"), \
         patch("agentic_traveler.orchestrator.agent.ConversationManager") as conv, \
         patch("agentic_traveler.orchestrator.agent.PreferenceLearner"), \
         patch("agentic_traveler.orchestrator.agent.get_client") as mock_get_client:
        conv.return_value.build_context_block.return_value = ""
        mock_client = MagicMock()
        mock_get_client.return_value = mock_client
        yield {
            "conversation": conv,
            "client": mock_client,
        }

def test_check_weather_registration(mock_user_tool, patched_deps):
    """Verify that check_weather is registered in the LLM config."""
    doc_ref = MagicMock()
    mock_user_tool.get_user_with_ref.return_value = (
        {"user_name": "Alice", "user_profile": {}}, doc_ref
    )
    
    mock_response = MagicMock()
    mock_response.text = "Hello!"
    patched_deps["client"].models.generate_content.return_value = mock_response

    agent = OrchestratorAgent(firestore_user_tool=mock_user_tool)
    agent.process_request("123", "Hello!")

    call_kwargs = patched_deps["client"].models.generate_content.call_args
    config = call_kwargs.kwargs.get("config") or call_kwargs[1].get("config")
    
    # Check if check_weather is in the tools list
    tool_names = [t.__name__ for t in config.tools]
    assert "check_weather" in tool_names

def test_check_weather_execution(mock_user_tool):
    """Verify the implementation of the check_weather method."""
    agent = OrchestratorAgent(firestore_user_tool=mock_user_tool)
    
    with patch("agentic_traveler.orchestrator.agent.WeatherService") as mock_weather_service:
        mock_weather_service.get_coordinates.return_value = {
            "lat": 51.5, "lng": -0.1, "name": "London", "country": "UK"
        }
        mock_weather_service.get_weather.return_value = {"daily": {"time": ["2026-03-08"]}}
        mock_weather_service.format_weather_summary.return_value = "Cloudy with a chance of meatballs"
        
        result = agent.check_weather("London")
        
        mock_weather_service.get_coordinates.assert_called_once_with("London")
        mock_weather_service.get_weather.assert_called_once()
        assert "Cloudy with a chance of meatballs" in result

def test_check_weather_unknown_location(mock_user_tool):
    """Verify handling of unknown locations in check_weather tool."""
    agent = OrchestratorAgent(firestore_user_tool=mock_user_tool)
    
    with patch("agentic_traveler.orchestrator.agent.WeatherService") as mock_weather_service:
        mock_weather_service.get_coordinates.return_value = None
        
        result = agent.check_weather("Atlantis")
        assert "couldn't find the location" in result
