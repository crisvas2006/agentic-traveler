"""
Integration tests for the IntentClassifier against the real Gemini API.

These tests verify that realistic user messages are classified into
the expected intent labels by the live LLM.
"""

import pytest
from agentic_traveler.orchestrator.intent_classifier import IntentClassifier


pytestmark = pytest.mark.integration


@pytest.fixture(scope="module")
def classifier():
    """A real IntentClassifier (no mocks)."""
    return IntentClassifier()


# Each tuple: (user message, expected intent)
INTENT_CASES = [
    # NEW_TRIP
    ("I want to go to Japan next spring", "NEW_TRIP"),
    ("Suggest me a cheap beach destination", "NEW_TRIP"),
    ("Where should I travel in August?", "NEW_TRIP"),
    # PLANNING
    ("Create a 5-day itinerary for Rome", "PLANNING"),
    ("Help me schedule my week in Barcelona", "PLANNING"),
    ("I need a detailed plan for my Tokyo trip", "PLANNING"),
    # IN_TRIP
    ("I'm exhausted from walking around the city, what should I do now?", "IN_TRIP"),
    ("What can I do near my hotel right now?", "IN_TRIP"),
    ("I'm bored, suggest something fun nearby", "IN_TRIP"),
    # CHAT
    ("Hello!", "CHAT"),
    ("Thanks for the help", "CHAT"),
    ("What can you do?", "CHAT"),
]


@pytest.mark.parametrize("message,expected_intent", INTENT_CASES)
def test_intent_classification(classifier, message, expected_intent):
    """The live LLM should classify each message into the expected intent."""
    result = classifier.classify(message)
    assert result == expected_intent, (
        f"Expected '{expected_intent}' for '{message}', got '{result}'"
    )
