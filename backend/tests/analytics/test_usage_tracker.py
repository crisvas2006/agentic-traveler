"""
Tests for the usage tracker module.

Since usage_tracker no longer writes to Firestore directly,
these tests verify token extraction, grounding detection, and
metrics_tracker integration.
"""

from unittest.mock import MagicMock, patch

from agentic_traveler.analytics.usage_tracker import log_and_accumulate


def _mock_response(prompt_tokens=100, candidates_tokens=50):
    """Build a mock GenAI response with usage_metadata."""
    usage = MagicMock()
    usage.prompt_token_count = prompt_tokens
    usage.candidates_token_count = candidates_tokens

    response = MagicMock()
    response.usage_metadata = usage
    # No grounding metadata by default
    response.candidates = []
    return response


def test_returns_token_counts():
    """log_and_accumulate returns correct token breakdown."""
    resp = _mock_response(prompt_tokens=200, candidates_tokens=80)
    result = log_and_accumulate(
        agent_name="test_agent",
        model_name="gemini-2.5-flash",
        user_id="user123",
        response=resp,
        latency_ms=500,
    )
    assert result["input_tokens"] == 200
    assert result["output_tokens"] == 80
    assert result["total_tokens"] == 280


def test_no_firestore_call_is_made():
    """Usage tracker does not make any Firestore calls (regression guard)."""
    resp = _mock_response(prompt_tokens=100, candidates_tokens=50)
    # Pass a mock as user_doc_ref — it should NEVER be called
    ref = MagicMock()
    with patch("agentic_traveler.analytics.metrics_tracker.record_token_usage"):
        log_and_accumulate(
            agent_name="test_agent",
            model_name="gemini-2.5-flash",
            user_id="user456",
            response=resp,
            latency_ms=300,
            user_doc_ref=ref,
        )
    # The ref object must never have any of its methods called
    ref.update.assert_not_called()
    ref.set.assert_not_called()


def test_no_accumulation_without_ref():
    """Passing user_doc_ref=None is accepted and returns correct counts."""
    resp = _mock_response()
    result = log_and_accumulate(
        agent_name="orchestrator",
        model_name="test-model",
        user_id="789",
        response=resp,
        latency_ms=100,
        user_doc_ref=None,
    )
    assert result["total_tokens"] == 150


def test_zero_tokens_no_metrics_call():
    """Zero-token responses don't call metrics_tracker.record_token_usage."""
    resp = _mock_response(prompt_tokens=0, candidates_tokens=0)

    with patch("agentic_traveler.analytics.metrics_tracker.record_token_usage") as mock_record:
        log_and_accumulate(
            agent_name="test",
            model_name="test-model",
            user_id="000",
            response=resp,
            latency_ms=10,
        )
    mock_record.assert_not_called()


def test_handles_missing_usage_metadata():
    """Responses without usage_metadata return zeroes gracefully."""
    resp = MagicMock(spec=[])  # no usage_metadata attribute
    result = log_and_accumulate(
        agent_name="test",
        model_name="test-model",
        user_id="000",
        response=resp,
        latency_ms=10,
    )
    assert result["input_tokens"] == 0
    assert result["output_tokens"] == 0
    assert result["total_tokens"] == 0


def test_grounding_detected():
    """Grounding detection returns True when grounding_chunks present."""
    candidate = MagicMock()
    candidate.grounding_metadata.grounding_chunks = [MagicMock()]

    resp = MagicMock()
    resp.candidates = [candidate]
    resp.usage_metadata.prompt_token_count = 100
    resp.usage_metadata.candidates_token_count = 50

    result = log_and_accumulate(
        agent_name="trip",
        model_name="gemini-3-flash-preview",
        user_id="000",
        response=resp,
        latency_ms=10,
    )
    assert result["grounding_used"] is True
    assert result["grounding_cost_credits"] >= 1
