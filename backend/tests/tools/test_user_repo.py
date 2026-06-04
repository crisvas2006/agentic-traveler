"""Tests for UserRepository profile operations."""

from unittest.mock import MagicMock, patch
from agentic_traveler.tools.user_repo import UserRepository


def test_upsert_structured_profile():
    """upsert_structured_profile should write the structured profile to profile_data and pop/write the summary column."""
    mock_db = MagicMock()
    
    # Mock the chain for UPSERT
    mock_upsert_chain = MagicMock()
    mock_db.table.return_value.upsert.return_value.execute.return_value = mock_upsert_chain

    profile = {
        "personality_dimensions_scores": {"exploration_tolerance": 0.8},
        "tags": ["Solo"],
        "summary": "This is a summary.",
        "tone_preference": "friendly"
    }

    with patch("agentic_traveler.tools.user_repo.get_db", return_value=mock_db):
        repo = UserRepository()
        repo.upsert_structured_profile("user-123", profile)

    # Check upsert query payload (summary popped, remaining is profile_data)
    expected_profile_data = {
        "personality_dimensions_scores": {"exploration_tolerance": 0.8},
        "tags": ["Solo"],
        "tone_preference": "friendly"
    }
    mock_db.table.assert_any_call("user_profiles")
    mock_db.table.return_value.upsert.assert_called_once_with({
        "user_id": "user-123",
        "profile_data": expected_profile_data,
        "summary": "This is a summary."
    })
