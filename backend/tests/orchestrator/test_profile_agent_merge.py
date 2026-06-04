"""Tests for ProfileAgent build_initial_profile merging logic."""

from unittest.mock import MagicMock, patch
from agentic_traveler.orchestrator.profile_agent import ProfileAgent


@patch("agentic_traveler.tools.db_client.get_db")
@patch("agentic_traveler.orchestrator.profile_agent.ProfileAgent._call_llm")
def test_build_initial_profile_no_existing(mock_call_llm, mock_get_db):
    """If no existing profile exists, build_initial_profile should analyze raw form data and use standard fallback."""
    mock_db = MagicMock()
    mock_get_db.return_value = mock_db

    # SELECT returns no profile
    mock_db.table.return_value.select.return_value.eq.return_value.maybe_single.return_value.execute.return_value.data = None

    mock_call_llm.return_value = ({"tags": ["New"]}, None, 100.0)

    agent = ProfileAgent()
    raw_form = {"question_1": "answer_1"}
    result, _, _ = agent.build_initial_profile(raw_form, user_uuid="user-123")

    assert result == {"tags": ["New"]}
    
    # Verify DB query
    mock_db.table.assert_any_call("user_profiles")
    mock_db.table.return_value.select.assert_called_with("profile_data, summary")
    
    # Verify LLM call
    mock_call_llm.assert_called_once()
    args = mock_call_llm.call_args[0]
    prompt = args[0]
    fallback_profile = mock_call_llm.call_args[1]["fallback_profile"]
    
    assert "FORM DATA" in prompt
    assert "question_1" in prompt
    assert "EXISTING PROFILE" not in prompt
    # Fallback should be the default fallback since no existing profile was found
    assert fallback_profile == agent._build_fallback()


@patch("agentic_traveler.tools.db_client.get_db")
@patch("agentic_traveler.orchestrator.profile_agent.ProfileAgent._call_llm")
def test_build_initial_profile_with_existing(mock_call_llm, mock_get_db):
    """If an existing profile exists, build_initial_profile should construct a merge prompt and merge fallbacks."""
    mock_db = MagicMock()
    mock_get_db.return_value = mock_db

    # SELECT returns existing profile
    mock_db.table.return_value.select.return_value.eq.return_value.maybe_single.return_value.execute.return_value.data = {
        "profile_data": {
            "trip_vibe": ["Adventure"],
            "diet": "Gluten-Free"
        },
        "summary": "Existing user summary."
    }

    mock_call_llm.return_value = ({"tags": ["Merged"]}, None, 100.0)

    agent = ProfileAgent()
    raw_form = {"question_1": "answer_1"}
    result, _, _ = agent.build_initial_profile(raw_form, user_uuid="user-123")

    assert result == {"tags": ["Merged"]}

    # Verify LLM call
    mock_call_llm.assert_called_once()
    args = mock_call_llm.call_args[0]
    prompt = args[0]
    fallback_profile = mock_call_llm.call_args[1]["fallback_profile"]

    # Prompt should request intelligent merge
    assert "EXISTING PROFILE" in prompt
    assert "NEW TALLY FORM SUBMISSION DATA" in prompt
    assert "INSTRUCTIONS FOR MERGING" in prompt
    assert "Adventure" in prompt
    assert "Gluten-Free" in prompt

    # Fallback profile should be default fallback merged with existing profile keys
    assert fallback_profile["trip_vibe"] == ["Adventure"]
    assert fallback_profile["diet"] == "Gluten-Free"
    assert fallback_profile["summary"] == "Existing user summary."
    assert "tags" in fallback_profile  # from default fallback


@patch("agentic_traveler.tools.db_client.get_db")
@patch("google.genai.Client")
def test_build_initial_profile_fallback_on_error(mock_client, mock_get_db):
    """If the LLM call throws an exception, build_initial_profile should return the merged fallback profile."""
    mock_db = MagicMock()
    mock_get_db.return_value = mock_db

    # SELECT returns existing profile with custom key
    mock_db.table.return_value.select.return_value.eq.return_value.maybe_single.return_value.execute.return_value.data = {
        "profile_data": {
            "custom_pref_key": "custom_val"
        },
        "summary": "Existing summary."
    }

    # Force generate_content to raise an exception
    mock_client.return_value.models.generate_content.side_effect = Exception("API Error")

    agent = ProfileAgent(client=mock_client.return_value)
    
    raw_form = {"question_1": "answer_1"}
    result, response, latency = agent.build_initial_profile(raw_form, user_uuid="user-123")

    # Should not crash, response should be None
    assert response is None
    # Result should have custom preference from existing profile preserved
    assert result["custom_pref_key"] == "custom_val"
    assert result["summary"] == "Existing summary."
    # Standard tags should be there from fallback base
    assert "tags" in result




