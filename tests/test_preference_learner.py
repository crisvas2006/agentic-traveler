"""Tests for the simplified PreferenceLearner (Firestore-only, no LLM)."""

import pytest
from unittest.mock import MagicMock
from agentic_traveler.orchestrator.preference_learner import PreferenceLearner


@pytest.fixture
def learner():
    return PreferenceLearner()


@pytest.fixture
def user_doc():
    return {
        "user_profile": {
            "trip_vibe": ["Adventure", "Nature"],
            "budget_priority": "mid-range",
        },
        "learned_extras": {},
    }


@pytest.fixture
def mock_ref():
    return MagicMock()


def test_save_known_scalar_field(learner, user_doc, mock_ref):
    """Known scalar field → updates user_profile."""
    learner.save_preference("budget_priority", "luxury", user_doc, mock_ref)

    mock_ref.set.assert_called_once()
    call_args = mock_ref.set.call_args[0][0]
    assert call_args["user_profile.budget_priority"] == "luxury"


def test_save_known_list_field_merges(learner, user_doc, mock_ref):
    """Known list field → merges rather than overwrites."""
    learner.save_preference("trip_vibe", "Beach", user_doc, mock_ref)

    call_args = mock_ref.set.call_args[0][0]
    merged = call_args["user_profile.trip_vibe"]
    assert "Beach" in merged
    assert "Adventure" in merged
    assert "Nature" in merged


def test_save_unknown_key_goes_to_extras(learner, user_doc, mock_ref):
    """Unknown key → stored in learned_extras."""
    learner.save_preference("preferred_airlines", "low-cost only", user_doc, mock_ref)

    call_args = mock_ref.set.call_args[0][0]
    assert call_args["learned_extras"]["preferred_airlines"] == "low-cost only"


def test_save_uses_merge(learner, user_doc, mock_ref):
    """Firestore writes use merge=True to avoid overwriting other fields."""
    learner.save_preference("budget_priority", "luxury", user_doc, mock_ref)
    assert mock_ref.set.call_args[1]["merge"] is True
