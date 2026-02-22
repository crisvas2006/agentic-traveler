import pytest
from unittest.mock import MagicMock
from agentic_traveler.orchestrator.safety_filter import SafetyFilter, _SAFETY_DISCLAIMER


@pytest.fixture
def mock_client():
    return MagicMock()


def test_safety_filter_uses_cheap_model(mock_client):
    sf = SafetyFilter(client=mock_client)
    assert sf.model_name == "gemini-2.5-flash-lite"


def test_safe_content_passes_through(mock_client):
    mock_response = MagicMock()
    mock_response.text = "SAFE"
    mock_client.models.generate_content.return_value = mock_response

    sf = SafetyFilter(client=mock_client)
    original = "Visit the Colosseum in the morning."
    assert sf.filter(original) == original


def test_disclaimer_appended_for_sensitive(mock_client):
    mock_response = MagicMock()
    mock_response.text = "SAFETY_DISCLAIMER_NEEDED"
    mock_client.models.generate_content.return_value = mock_response

    sf = SafetyFilter(client=mock_client)
    original = "Try cliff jumping at the local quarry."
    result = sf.filter(original)
    assert result.startswith(original)
    assert "Please verify details and safety" in result


def test_rewrite_for_unsafe_content(mock_client):
    mock_response = MagicMock()
    mock_response.text = "Visit the beach instead — it's a safer and fun option."
    mock_client.models.generate_content.return_value = mock_response

    sf = SafetyFilter(client=mock_client)
    result = sf.filter("Go trespassing in the abandoned factory.")
    assert "beach" in result
    assert "trespassing" not in result


def test_fallback_on_exception(mock_client):
    mock_client.models.generate_content.side_effect = RuntimeError("boom")

    sf = SafetyFilter(client=mock_client)
    # Contains a sensitive keyword — fallback should add disclaimer
    result = sf.filter("Walk alone at night through the dangerous area.")
    assert "Please verify details and safety" in result


def test_fallback_safe_no_keywords(mock_client):
    mock_client.models.generate_content.side_effect = RuntimeError("boom")

    sf = SafetyFilter(client=mock_client)
    original = "Have a nice coffee at the local café."
    assert sf.filter(original) == original


def test_keyword_fallback_no_client():
    sf = SafetyFilter(client=None)
    # Contains "illegal" keyword
    result = sf.filter("There are illegal street food stalls nearby.")
    assert "Please verify details and safety" in result
