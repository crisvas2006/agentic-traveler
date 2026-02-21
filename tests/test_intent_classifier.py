import pytest
from unittest.mock import MagicMock, patch
from agentic_traveler.orchestrator.intent_classifier import IntentClassifier


@pytest.fixture
def mock_genai_client():
    with patch("agentic_traveler.orchestrator.intent_classifier.genai.Client") as mock:
        yield mock


def test_classifier_uses_cheap_model(mock_genai_client):
    clf = IntentClassifier(api_key="test_key")
    assert clf.model_name == "gemini-2.5-flash-lite"


def test_classify_new_trip(mock_genai_client):
    mock_response = MagicMock()
    mock_response.text = "NEW_TRIP"
    mock_genai_client.return_value.models.generate_content.return_value = mock_response

    clf = IntentClassifier(api_key="test_key")
    assert clf.classify("I want to go to Japan") == "NEW_TRIP"


def test_classify_planning(mock_genai_client):
    mock_response = MagicMock()
    mock_response.text = "PLANNING"
    mock_genai_client.return_value.models.generate_content.return_value = mock_response

    clf = IntentClassifier(api_key="test_key")
    assert clf.classify("Build me a detailed itinerary for Rome") == "PLANNING"


def test_classify_in_trip(mock_genai_client):
    mock_response = MagicMock()
    mock_response.text = "IN_TRIP"
    mock_genai_client.return_value.models.generate_content.return_value = mock_response

    clf = IntentClassifier(api_key="test_key")
    assert clf.classify("I'm tired and hungry, what should I do?") == "IN_TRIP"


def test_classify_chat(mock_genai_client):
    mock_response = MagicMock()
    mock_response.text = "CHAT"
    mock_genai_client.return_value.models.generate_content.return_value = mock_response

    clf = IntentClassifier(api_key="test_key")
    assert clf.classify("Hello there!") == "CHAT"


def test_classify_fallback_on_bad_label(mock_genai_client):
    """If the LLM returns garbage, the classifier falls back to keywords."""
    mock_response = MagicMock()
    mock_response.text = "UNKNOWN_LABEL"
    mock_genai_client.return_value.models.generate_content.return_value = mock_response

    clf = IntentClassifier(api_key="test_key")
    # "trip" keyword triggers NEW_TRIP in fallback
    assert clf.classify("I want a trip") == "NEW_TRIP"


def test_classify_fallback_on_exception(mock_genai_client):
    """If the LLM call raises, the classifier falls back to keywords."""
    mock_genai_client.return_value.models.generate_content.side_effect = RuntimeError("boom")

    clf = IntentClassifier(api_key="test_key")
    assert clf.classify("I'm bored here") == "IN_TRIP"


def test_classify_no_api_key():
    """Without an API key, the classifier uses keyword fallback."""
    with patch.dict("os.environ", {}, clear=True):
        with patch("agentic_traveler.orchestrator.intent_classifier.genai.Client"):
            clf = IntentClassifier(api_key=None)
            clf.client = None
            assert clf.classify("Plan a vacation") == "NEW_TRIP"
