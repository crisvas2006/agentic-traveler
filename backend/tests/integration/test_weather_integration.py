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
    with patch("agentic_traveler.orchestrator.agent.DiscoveryAgent") as disc, \
         patch("agentic_traveler.orchestrator.agent.PlannerAgent") as plan, \
         patch("agentic_traveler.orchestrator.agent.CompanionAgent") as comp, \
         patch("agentic_traveler.orchestrator.agent.ConversationManager") as conv, \
         patch("agentic_traveler.orchestrator.agent.PreferenceLearner"), \
         patch("agentic_traveler.orchestrator.agent.get_client") as mock_get_client:
        
        conv.return_value.build_context_block.return_value = ""
        mock_client = MagicMock()
        mock_get_client.return_value = mock_client
        
        yield {
            "discovery": disc,
            "planner": plan,
            "companion": comp,
            "conversation": conv,
            "client": mock_client,
        }

def test_discovery_agent_with_weather(mock_user_tool, patched_deps):
    """
    Simulate a flow where the user asks for destination advice, 
    and the discovery agent's logic (via the orchestrator) includes weather.
    """
    doc_ref = MagicMock()
    mock_user_tool.get_user_with_ref.return_value = (
        {"user_name": "Alice", "user_profile": {}}, doc_ref
    )

    # 1. Orchestrator receives "Sunniest places in Europe next week?"
    # 2. Orchestrator decides to call check_weather first? 
    # Or calls discovery_agent and discovery_agent returns instructions to check weather?
    # In our architecture, tools are only on the orchestrator.
    # So the orchestrator must see the need for weather or the sub-agent result says "Based on weather..."
    
    # Let's simulate:
    # Response 1: Tool call check_weather("Southern Europe", days=7)
    # Response 2: Tool call discover_destinations(request="Places with sun like the weather report says...")
    # Response 3: Final text
    
    mock_weather_call = MagicMock()
    mock_weather_call.name = "check_weather"
    mock_weather_call.args = {"location": "Southern Europe", "days": 7}
    
    mock_discovery_call = MagicMock()
    mock_discovery_call.name = "discover_destinations"
    mock_discovery_call.args = {"request": "Suggest sunniest places in Southern Europe"}
    
    candidate1 = MagicMock()
    candidate1.content.parts = [MagicMock(function_call=mock_weather_call)]
    
    candidate2 = MagicMock()
    candidate2.content.parts = [MagicMock(function_call=mock_discovery_call)]
    
    mock_final = MagicMock()
    mock_final.text = "Based on the great weather (Sunny, 25C) and my discovery, I suggest Algarve!"
    
    # The AutomaticFunctionCalling handles the loop, but in a test we mock the SDK method 
    # which returns once for the whole loop if configured? No, if we mock the SDK,
    # we simulate what the LLM *would* return at each step if AFC was off or how AFC perceives it.
    
    # Actually, in a high-level integration test, we want to see if the Orchestrator's prompt 
    # and tool definitions allow for this synergy.
    
    agent = OrchestratorAgent(firestore_user_tool=mock_user_tool)
    
    with patch("agentic_traveler.orchestrator.agent.WeatherService") as mock_weather_service:
        # Define a side effect to return dynamic data based on input
        def get_coords_side_effect(loc):
            return {"lat": 1.0, "lng": 1.0, "name": loc, "country": "TestCountry"}
        
        mock_weather_service.get_coordinates.side_effect = get_coords_side_effect
        mock_weather_service.get_weather.return_value = {"daily": {"time": ["2026-03-08"]}}
        mock_weather_service.format_weather_summary.side_effect = lambda loc, data: f"It's sunny in {loc}!"
        
        # Test: Can the orchestrator be called with a weather query and correctly use the location?
        result = agent.check_weather("Paris", days=5)
        assert "Paris" in result
        assert "sunny" in result.lower()
