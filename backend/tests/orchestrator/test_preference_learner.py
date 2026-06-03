"""Tests for the ProfileAgent.save_preference method."""

import pytest
from unittest.mock import MagicMock, patch
from agentic_traveler.orchestrator.profile_agent import ProfileAgent


@pytest.fixture
def user_doc():
    return {
        "user_profile": {
            "trip_vibe": ["Adventure", "Nature"],
            "budget_priority": "mid-range",
        },
        "learned_extras": {},
    }


@patch("agentic_traveler.tools.db_client.get_db")
@patch("agentic_traveler.orchestrator.profile_agent.ProfileAgent.update_profile")
@patch("agentic_traveler.analytics.usage_tracker.log_and_accumulate")
@patch("agentic_traveler.economy.credit_manager.record_usage_and_bill")
def test_save_known_scalar_field(mock_bill, mock_log, mock_update, mock_get_db, user_doc):
    """Known scalar field -> updates local data, calls LLM update, and bills immediately if token_records is None."""
    mock_db = MagicMock()
    mock_get_db.return_value = mock_db
    
    # Explicitly mock database select query chain
    mock_query = MagicMock()
    mock_db.table.return_value = mock_query
    
    mock_select = MagicMock()
    mock_query.select.return_value = mock_select
    
    mock_eq = MagicMock()
    mock_select.eq.return_value = mock_eq
    
    mock_maybe = MagicMock()
    mock_eq.maybe_single.return_value = mock_maybe
    
    mock_execute = MagicMock()
    mock_maybe.execute.return_value = mock_execute
    mock_execute.data = {
        "profile_data": {
            "trip_vibe": ["Adventure", "Nature"],
            "budget_priority": "mid-range",
        },
        "summary": "Old summary."
    }
    
    # Mock update_profile LLM response (structured_data, response, latency)
    mock_response = MagicMock()
    mock_update.return_value = (
        {"budget_priority": "luxury", "summary": "Likes luxury."},
        mock_response,
        1500.0
    )
    
    # Mock usage_tracker
    mock_log.return_value = {
        "input_tokens": 100,
        "output_tokens": 50,
    }
    
    agent = ProfileAgent()
    agent.save_preference("budget_priority", "luxury", user_doc, "user-uuid-123", _sync=True)

    # Check update_profile is called with correct context
    mock_update.assert_called_once_with(
        "The user indicated their 'budget_priority' preference is: luxury",
        {
            "trip_vibe": ["Adventure", "Nature"],
            "budget_priority": "luxury",
            "summary": "Old summary.",
        }
    )

    # Check database calls
    mock_db.table.assert_any_call("user_profiles")
    mock_query.upsert.assert_called_once_with({
        "user_id": "user-uuid-123",
        "profile_data": {
            "trip_vibe": ["Adventure", "Nature"],
            "budget_priority": "luxury",
        },
        "summary": "Likes luxury."
    })

    # Since token_records is None, check immediate billing
    mock_bill.assert_called_once_with(
        user_id="user-uuid-123",
        token_records=[{
            "model_name": agent._model_name,
            "input_tokens": 100,
            "output_tokens": 50,
            "agent_name": "profile_agent",
        }],
        default_agent_name="profile_agent",
        run_async=False,
    )


@patch("agentic_traveler.tools.db_client.get_db")
@patch("agentic_traveler.orchestrator.profile_agent.ProfileAgent.update_profile")
@patch("agentic_traveler.analytics.usage_tracker.log_and_accumulate")
@patch("agentic_traveler.economy.credit_manager.record_usage_and_bill")
def test_save_known_list_field_merges(mock_bill, mock_log, mock_update, mock_get_db, user_doc):
    """Known list field -> merges values, calls LLM, and updates database."""
    mock_db = MagicMock()
    mock_get_db.return_value = mock_db
    
    # Explicitly mock database select query chain
    mock_query = MagicMock()
    mock_db.table.return_value = mock_query
    
    mock_select = MagicMock()
    mock_query.select.return_value = mock_select
    
    mock_eq = MagicMock()
    mock_select.eq.return_value = mock_eq
    
    mock_maybe = MagicMock()
    mock_eq.maybe_single.return_value = mock_maybe
    
    mock_execute = MagicMock()
    mock_maybe.execute.return_value = mock_execute
    mock_execute.data = {
        "profile_data": {
            "trip_vibe": ["Adventure", "Nature"],
            "budget_priority": "mid-range",
        },
        "summary": "Old summary."
    }
    
    # Mock update_profile
    mock_response = MagicMock()
    mock_update.return_value = (
        {"trip_vibe": ["Adventure", "Nature", "Beach"], "summary": "Likes beach."},
        mock_response,
        1500.0
    )
    mock_log.return_value = {
        "input_tokens": 100,
        "output_tokens": 50,
    }
    
    agent = ProfileAgent()
    agent.save_preference("trip_vibe", "Beach", user_doc, "user-uuid-123", _sync=True)

    # Check update_profile is called with correctly merged list
    mock_update.assert_called_once_with(
        "The user indicated their 'trip_vibe' preference is: Beach",
        {
            "trip_vibe": ["Adventure", "Nature", "Beach"],
            "budget_priority": "mid-range",
            "summary": "Old summary.",
        }
    )

    mock_query.upsert.assert_called_once_with({
        "user_id": "user-uuid-123",
        "profile_data": {
            "trip_vibe": ["Adventure", "Nature", "Beach"],
            "budget_priority": "mid-range",
        },
        "summary": "Likes beach."
    })


@patch("agentic_traveler.tools.db_client.get_db")
@patch("agentic_traveler.orchestrator.profile_agent.ProfileAgent.update_profile")
@patch("agentic_traveler.analytics.usage_tracker.log_and_accumulate")
@patch("agentic_traveler.economy.credit_manager.record_usage_and_bill")
def test_save_with_token_records_accumulates(mock_bill, mock_log, mock_update, mock_get_db, user_doc):
    """If token_records list is provided, appends token usage and bypasses immediate billing."""
    mock_db = MagicMock()
    mock_get_db.return_value = mock_db
    
    # Explicitly mock database select query chain
    mock_query = MagicMock()
    mock_db.table.return_value = mock_query
    
    mock_select = MagicMock()
    mock_query.select.return_value = mock_select
    
    mock_eq = MagicMock()
    mock_select.eq.return_value = mock_eq
    
    mock_maybe = MagicMock()
    mock_eq.maybe_single.return_value = mock_maybe
    
    mock_execute = MagicMock()
    mock_maybe.execute.return_value = mock_execute
    mock_execute.data = {
        "profile_data": {
            "trip_vibe": ["Adventure", "Nature"],
            "budget_priority": "mid-range",
        },
        "summary": "Old summary."
    }
    
    mock_response = MagicMock()
    mock_update.return_value = (
        {"budget_priority": "luxury", "summary": "Likes luxury."},
        mock_response,
        1500.0
    )
    mock_log.return_value = {
        "input_tokens": 100,
        "output_tokens": 50,
    }
    
    agent = ProfileAgent()
    token_records = []
    agent.save_preference("budget_priority", "luxury", user_doc, "user-uuid-123", _sync=True, token_records=token_records)

    # Check token_records contains the record
    assert len(token_records) == 1
    assert token_records[0] == {
        "model_name": agent._model_name,
        "input_tokens": 100,
        "output_tokens": 50,
        "agent_name": "profile_agent",
    }

    # Bypasses immediate billing
    mock_bill.assert_not_called()
