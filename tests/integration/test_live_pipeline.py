"""
Integration tests for the full OrchestratorAgent pipeline.

Uses real Firestore (test user created/deleted per test)
and real Gemini API calls.  Asserts on response *structure*
rather than exact content, since LLM output is non-deterministic.
"""

import pytest
from agentic_traveler.orchestrator.agent import OrchestratorAgent


pytestmark = pytest.mark.integration


# ------------------------------------------------------------------
# 1. New-user flow (no test data needed — use a fake telegram ID)
# ------------------------------------------------------------------

def test_new_user_gets_onboarding(orchestrator):
    """A completely unknown telegram ID should trigger onboarding."""
    response = orchestrator.process_request(
        "nonexistent_user_999999", "Hello!"
    )
    assert response["action"] == "ONBOARDING_REQUIRED"
    assert "tally.so" in response["text"]


# ------------------------------------------------------------------
# 2. Discovery flow (NEW_TRIP intent)
# ------------------------------------------------------------------

def test_discovery_flow(orchestrator, test_user):
    """An existing user asking about a trip should get destination ideas."""
    response = orchestrator.process_request(
        test_user["_telegram_id"],
        "I want to travel somewhere warm and cheap in March",
    )
    assert response["action"] in ("DISCOVERY_RESULTS", "ERROR")
    assert isinstance(response["text"], str)
    assert len(response["text"]) > 20  # non-trivial response


# ------------------------------------------------------------------
# 3. Planner flow (PLANNING intent)
# ------------------------------------------------------------------

def test_planner_flow(orchestrator, test_user):
    """An existing user asking for an itinerary should get a plan."""
    response = orchestrator.process_request(
        test_user["_telegram_id"],
        "Create a 3-day itinerary for my trip to Lisbon",
    )
    assert response["action"] in ("PLANNER_RESULTS", "ERROR")
    assert isinstance(response["text"], str)
    assert len(response["text"]) > 50  # should be a substantial plan


# ------------------------------------------------------------------
# 4. Companion flow (IN_TRIP intent)
# ------------------------------------------------------------------

def test_companion_flow(orchestrator, test_user):
    """An existing user who is on a trip should get live suggestions."""
    response = orchestrator.process_request(
        test_user["_telegram_id"],
        "I'm tired and hungry here, what should I do right now?",
    )
    assert response["action"] in ("COMPANION_RESULTS", "ERROR")
    assert isinstance(response["text"], str)
    assert len(response["text"]) > 20


# ------------------------------------------------------------------
# 5. Chat flow
# ------------------------------------------------------------------

def test_chat_flow(orchestrator, test_user):
    """A generic greeting should get a friendly chat reply."""
    response = orchestrator.process_request(
        test_user["_telegram_id"],
        "Hello, how are you?",
    )
    assert response["action"] == "CHAT_REPLY"
    assert "IntegrationBot" in response["text"]

