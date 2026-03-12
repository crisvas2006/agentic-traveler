"""
Tests for the usage tracker module.

Uses mocks for the Firestore DocumentReference — no real Firestore calls.
"""

from unittest.mock import MagicMock

from agentic_traveler.usage_tracker import log_and_accumulate


def _mock_response(prompt_tokens=100, candidates_tokens=50):
    """Build a mock GenAI response with usage_metadata."""
    usage = MagicMock()
    usage.prompt_token_count = prompt_tokens
    usage.candidates_token_count = candidates_tokens

    response = MagicMock()
    response.usage_metadata = usage
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


def test_accumulates_to_firestore():
    """Token totals are written to Firestore with atomic increments."""
    ref = MagicMock()
    resp = _mock_response(prompt_tokens=100, candidates_tokens=50)

    log_and_accumulate(
        agent_name="test_agent",
        model_name="gemini-2.5-flash",
        user_id="user456",
        response=resp,
        latency_ms=300,
        user_doc_ref=ref,
    )

    ref.update.assert_called_once()
    call_args = ref.update.call_args[0][0]
    # Model name dots replaced with underscores for Firestore paths
    assert "usage.gemini-2_5-flash.total_input_tokens" in call_args
    assert "usage.gemini-2_5-flash.total_output_tokens" in call_args
    assert "usage.gemini-2_5-flash.call_count" in call_args


def test_no_accumulation_without_ref():
    """Without a doc ref, no Firestore call is made."""
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


def test_no_accumulation_for_zero_tokens():
    """Zero-token responses don't trigger Firestore writes."""
    ref = MagicMock()
    resp = _mock_response(prompt_tokens=0, candidates_tokens=0)

    log_and_accumulate(
        agent_name="test",
        model_name="test-model",
        user_id="000",
        response=resp,
        latency_ms=10,
        user_doc_ref=ref,
    )
    ref.update.assert_not_called()


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


def test_firestore_error_does_not_raise():
    """Firestore write failure is logged but does not crash."""
    ref = MagicMock()
    ref.update.side_effect = RuntimeError("Firestore down")

    resp = _mock_response()
    # Should not raise
    result = log_and_accumulate(
        agent_name="test",
        model_name="test-model",
        user_id="000",
        response=resp,
        latency_ms=10,
        user_doc_ref=ref,
    )
    assert result["total_tokens"] == 150
