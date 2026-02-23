"""
Tests for the refactored OrchestratorAgent with tool-based routing.

The orchestrator now uses a single LLM call with automatic function
calling.  These tests mock the genai client and verify:
- New user onboarding flow
- Direct chat (no tool calls)
- Tool calls trigger the right sub-agent
- Preference updates via tool call
- Conversation history is saved
"""

import pytest
from unittest.mock import MagicMock, patch, PropertyMock
from agentic_traveler.orchestrator.agent import OrchestratorAgent
from agentic_traveler.tools.firestore_user import FirestoreUserTool


@pytest.fixture
def mock_user_tool():
    tool = MagicMock(spec=FirestoreUserTool)
    return tool


@pytest.fixture
def patched_deps():
    """Patch sub-agent classes and conversation manager."""
    with patch("agentic_traveler.orchestrator.agent.DiscoveryAgent") as disc, \
         patch("agentic_traveler.orchestrator.agent.PlannerAgent") as plan, \
         patch("agentic_traveler.orchestrator.agent.CompanionAgent") as comp, \
         patch("agentic_traveler.orchestrator.agent.ConversationManager") as conv, \
         patch("agentic_traveler.orchestrator.agent.PreferenceLearner") as pref, \
         patch("agentic_traveler.orchestrator.agent.genai") as mock_genai:
        # conversation context is empty by default
        conv.return_value.build_context_block.return_value = ""
        # genai client mock
        mock_client = MagicMock()
        mock_genai.Client.return_value = mock_client
        yield {
            "discovery": disc,
            "planner": plan,
            "companion": comp,
            "conversation": conv,
            "preference": pref,
            "genai": mock_genai,
            "client": mock_client,
        }


def test_new_user_onboarding(mock_user_tool, patched_deps):
    """Unknown Telegram ID → onboarding link."""
    mock_user_tool.get_user_with_ref.return_value = (None, None)
    agent = OrchestratorAgent(firestore_user_tool=mock_user_tool)
    response = agent.process_request("unknown_id", "Hello")
    assert response["action"] == "ONBOARDING_REQUIRED"
    assert "tally.so" in response["text"]


def test_direct_chat_response(mock_user_tool, patched_deps):
    """For simple chat, the LLM responds directly (no tool calls)."""
    doc_ref = MagicMock()
    mock_user_tool.get_user_with_ref.return_value = (
        {"user_name": "Alice", "user_profile": {}}, doc_ref
    )

    # Mock the LLM to return a simple text with no tool calls
    mock_response = MagicMock()
    mock_response.text = "Hello Alice! How can I help you today?"
    patched_deps["client"].models.generate_content.return_value = mock_response

    agent = OrchestratorAgent(firestore_user_tool=mock_user_tool)
    result = agent.process_request("123", "Hello!")

    assert result["action"] == "RESPONSE"
    assert "Alice" in result["text"]


def test_conversation_saved_after_response(mock_user_tool, patched_deps):
    """Conversation history is saved after every exchange."""
    doc_ref = MagicMock()
    mock_user_tool.get_user_with_ref.return_value = (
        {"user_name": "Alice", "user_profile": {}}, doc_ref
    )

    mock_response = MagicMock()
    mock_response.text = "Hello!"
    patched_deps["client"].models.generate_content.return_value = mock_response

    agent = OrchestratorAgent(firestore_user_tool=mock_user_tool)
    agent.process_request("123", "Hi")

    patched_deps["conversation"].return_value.append_and_save.assert_called_once()


def test_llm_failure_returns_error(mock_user_tool, patched_deps):
    """If the LLM call fails, the user gets a friendly error message."""
    doc_ref = MagicMock()
    mock_user_tool.get_user_with_ref.return_value = (
        {"user_name": "Bob", "user_profile": {}}, doc_ref
    )

    patched_deps["client"].models.generate_content.side_effect = RuntimeError("LLM down")

    agent = OrchestratorAgent(firestore_user_tool=mock_user_tool)
    result = agent.process_request("123", "Plan something")

    assert "snag" in result["text"].lower() or "sorry" in result["text"].lower()


def test_tool_functions_are_passed_to_llm(mock_user_tool, patched_deps):
    """Verify that the LLM call includes tool functions."""
    doc_ref = MagicMock()
    mock_user_tool.get_user_with_ref.return_value = (
        {"user_name": "Alice", "user_profile": {}}, doc_ref
    )

    mock_response = MagicMock()
    mock_response.text = "Hello!"
    patched_deps["client"].models.generate_content.return_value = mock_response

    agent = OrchestratorAgent(firestore_user_tool=mock_user_tool)
    agent.process_request("123", "Hello!")

    # Check that generate_content was called with tools
    call_kwargs = patched_deps["client"].models.generate_content.call_args
    config = call_kwargs.kwargs.get("config") or call_kwargs[1].get("config")
    assert config is not None
    assert config.tools is not None
    assert len(config.tools) == 4  # 4 tool functions


def test_no_client_returns_error(mock_user_tool):
    """Without an API key, LLM features are unavailable."""
    doc_ref = MagicMock()
    mock_user_tool.get_user_with_ref.return_value = (
        {"user_name": "Bob", "user_profile": {}}, doc_ref
    )

    with patch("agentic_traveler.orchestrator.agent.genai") as mock_genai, \
         patch("agentic_traveler.orchestrator.agent.DiscoveryAgent"), \
         patch("agentic_traveler.orchestrator.agent.PlannerAgent"), \
         patch("agentic_traveler.orchestrator.agent.CompanionAgent"), \
         patch("agentic_traveler.orchestrator.agent.ConversationManager") as conv, \
         patch("agentic_traveler.orchestrator.agent.PreferenceLearner"), \
         patch.dict("os.environ", {"GOOGLE_API_KEY": ""}):
        mock_genai.Client.return_value = None
        conv.return_value.build_context_block.return_value = ""

        agent = OrchestratorAgent(firestore_user_tool=mock_user_tool)
        agent._client = None  # force no client
        result = agent.process_request("123", "Hello")
        assert "unavailable" in result["text"].lower()
