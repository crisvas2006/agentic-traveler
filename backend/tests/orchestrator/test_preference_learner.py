"""Tests for the simplified PreferenceLearner (Firestore-only, no LLM)."""

import pytest
from unittest.mock import MagicMock, patch
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
    """Known scalar field → updates user_profile via ProfileAgent."""
    with patch("agentic_traveler.orchestrator.profile_agent.ProfileAgent") as mock_agent_class:
        mock_agent = mock_agent_class.return_value
        mock_agent.update_profile.return_value = {"budget_priority": "luxury"}
        
        learner.save_preference("budget_priority", "luxury", user_doc, mock_ref, _sync=True)

        mock_ref.set.assert_called_once()
        call_args = mock_ref.set.call_args[0][0]
        assert call_args["user_profile"] == {"budget_priority": "luxury"}


def test_save_known_list_field_merges(learner, user_doc, mock_ref):
    """ProfileAgent is responsible for merging; PreferenceLearner just passes data."""
    with patch("agentic_traveler.orchestrator.profile_agent.ProfileAgent") as mock_agent_class:
        mock_agent = mock_agent_class.return_value
        # Mock what the ProfileAgent would theoretically return after merging
        mock_agent.update_profile.return_value = {
            "trip_vibe": ["Adventure", "Nature", "Beach"],
            "budget_priority": "mid-range"
        }
        
        learner.save_preference("trip_vibe", "Beach", user_doc, mock_ref, _sync=True)

        call_args = mock_ref.set.call_args[0][0]
        merged = call_args["user_profile"]["trip_vibe"]
        assert "Beach" in merged
        assert "Adventure" in merged


def test_save_unknown_key_passes_to_agent(learner, user_doc, mock_ref):
    """Unknown keys are just passed to the ProfileAgent fact string."""
    with patch("agentic_traveler.orchestrator.profile_agent.ProfileAgent") as mock_agent_class:
        mock_agent = mock_agent_class.return_value
        mock_agent.update_profile.return_value = {"additional_info": "Prefers low-cost"}
        
        learner.save_preference("preferred_airlines", "low-cost only", user_doc, mock_ref, _sync=True)

        mock_agent.update_profile.assert_called_once()
        fact = mock_agent.update_profile.call_args[0][0]
        assert "preferred_airlines" in fact
        assert "low-cost only" in fact


def test_save_uses_merge(learner, user_doc, mock_ref):
    """Firestore writes use merge=True to avoid overwriting other fields."""
    with patch("agentic_traveler.orchestrator.profile_agent.ProfileAgent") as mock_agent_class:
        learner.save_preference("budget_priority", "luxury", user_doc, mock_ref, _sync=True)
        assert mock_ref.set.call_args[1]["merge"] is True
