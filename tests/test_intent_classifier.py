import pytest
from unittest.mock import MagicMock, patch
from agentic_traveler.orchestrator.intent_classifier import IntentClassifier


@pytest.fixture
def mock_client():
    """Provide a mock genai.Client."""
    client = MagicMock()
    return client


def test_classifier_uses_cheap_model():
    clf = IntentClassifier(client=MagicMock())
    assert clf.model_name == "gemini-2.5-flash-lite"


def test_classify_new_trip(mock_client):
    mock_response = MagicMock()
    mock_response.text = "NEW_TRIP|NO_PREF"
    mock_client.models.generate_content.return_value = mock_response

    clf = IntentClassifier(client=mock_client)
    intent, has_pref = clf.classify("I want to go to Japan")
    assert intent == "NEW_TRIP"
    assert has_pref is False


def test_classify_planning(mock_client):
    mock_response = MagicMock()
    mock_response.text = "PLANNING|NO_PREF"
    mock_client.models.generate_content.return_value = mock_response

    clf = IntentClassifier(client=mock_client)
    intent, has_pref = clf.classify("Build me a detailed itinerary for Rome")
    assert intent == "PLANNING"
    assert has_pref is False


def test_classify_in_trip(mock_client):
    mock_response = MagicMock()
    mock_response.text = "IN_TRIP|NO_PREF"
    mock_client.models.generate_content.return_value = mock_response

    clf = IntentClassifier(client=mock_client)
    intent, has_pref = clf.classify("I'm tired and hungry, what should I do?")
    assert intent == "IN_TRIP"
    assert has_pref is False


def test_classify_chat(mock_client):
    mock_response = MagicMock()
    mock_response.text = "CHAT|NO_PREF"
    mock_client.models.generate_content.return_value = mock_response

    clf = IntentClassifier(client=mock_client)
    intent, has_pref = clf.classify("Hello there!")
    assert intent == "CHAT"
    assert has_pref is False


def test_classify_with_preference_flag(mock_client):
    """When the message contains a preference, the flag should be True."""
    mock_response = MagicMock()
    mock_response.text = "CHAT|PREF"
    mock_client.models.generate_content.return_value = mock_response

    clf = IntentClassifier(client=mock_client)
    intent, has_pref = clf.classify("I hate crowded beaches")
    assert intent == "CHAT"
    assert has_pref is True


def test_classify_new_trip_with_preference(mock_client):
    """Intent + preference can co-occur."""
    mock_response = MagicMock()
    mock_response.text = "NEW_TRIP|PREF"
    mock_client.models.generate_content.return_value = mock_response

    clf = IntentClassifier(client=mock_client)
    intent, has_pref = clf.classify("I want somewhere tropical on a budget")
    assert intent == "NEW_TRIP"
    assert has_pref is True


def test_classify_fallback_on_bad_label(mock_client):
    """If the LLM returns garbage, the classifier falls back to keywords."""
    mock_response = MagicMock()
    mock_response.text = "UNKNOWN_LABEL"
    mock_client.models.generate_content.return_value = mock_response

    clf = IntentClassifier(client=mock_client)
    intent, has_pref = clf.classify("I want a trip")
    # "trip" keyword triggers NEW_TRIP in fallback
    assert intent == "NEW_TRIP"
    # Fallback doesn't detect preference
    assert has_pref is False


def test_classify_fallback_on_exception(mock_client):
    """If the LLM call raises, the classifier falls back to keywords."""
    mock_client.models.generate_content.side_effect = RuntimeError("boom")

    clf = IntentClassifier(client=mock_client)
    intent, has_pref = clf.classify("I'm bored here")
    assert intent == "IN_TRIP"
    assert has_pref is False


def test_keyword_fallback_no_client():
    """Without a client, the classifier uses keyword fallback."""
    clf = IntentClassifier(client=None)
    intent, has_pref = clf.classify("Plan a vacation")
    assert intent == "NEW_TRIP"
    assert has_pref is False
