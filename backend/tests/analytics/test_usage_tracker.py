"""
Tests for the usage tracker module.

Since usage_tracker no longer writes to Firestore directly,
these tests verify token extraction, grounding detection,
credit calculations, and both metrics_tracker and Supabase integrations.
"""

from unittest.mock import MagicMock, patch
import pytest

from agentic_traveler.analytics.usage_tracker import log_and_accumulate
from agentic_traveler.orchestrator.agent import _save_and_finish


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


@patch("agentic_traveler.analytics.usage_tracker._resolve_user_uuid", return_value="test-uuid-123")
@patch("agentic_traveler.tools.db_client.get_db")
def test_returns_token_counts(mock_get_db, mock_resolve):
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
    assert "total_cost_credits" in result


@patch("agentic_traveler.analytics.usage_tracker._resolve_user_uuid", return_value="test-uuid-123")
@patch("agentic_traveler.tools.db_client.get_db")
def test_no_firestore_call_is_made(mock_get_db, mock_resolve):
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


@patch("agentic_traveler.analytics.usage_tracker._resolve_user_uuid", return_value="test-uuid-123")
@patch("agentic_traveler.tools.db_client.get_db")
def test_no_accumulation_without_ref(mock_get_db, mock_resolve):
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


@patch("agentic_traveler.analytics.usage_tracker._resolve_user_uuid", return_value="test-uuid-123")
@patch("agentic_traveler.tools.db_client.get_db")
def test_zero_tokens_no_metrics_call(mock_get_db, mock_resolve):
    """Zero-token responses don't call metrics_tracker.record_token_usage."""
    resp = _mock_response(prompt_tokens=0, candidates_tokens=0)

    with patch("agentic_traveler.analytics.metrics_tracker.record_token_usage") as mock_record:
        log_and_accumulate(
            agent_name="test",
            model_name="test-model",
            user_id="system", # needs to be system to try to log directly
            response=resp,
            latency_ms=10,
        )
    mock_record.assert_not_called()


@patch("agentic_traveler.analytics.usage_tracker._resolve_user_uuid", return_value="test-uuid-123")
@patch("agentic_traveler.tools.db_client.get_db")
def test_handles_missing_usage_metadata(mock_get_db, mock_resolve):
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


@patch("agentic_traveler.analytics.usage_tracker._resolve_user_uuid", return_value="test-uuid-123")
@patch("agentic_traveler.tools.db_client.get_db")
def test_grounding_detected(mock_get_db, mock_resolve):
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


@patch("agentic_traveler.analytics.usage_tracker._resolve_user_uuid", return_value="test-uuid-123")
@patch("agentic_traveler.tools.db_client.get_db")
def test_usage_tracking_database_accumulation_system_compaction(mock_get_db, mock_resolve):
    """log_and_accumulate issues direct metrics_tracker call for system compaction."""
    resp = _mock_response(prompt_tokens=150, candidates_tokens=70)
    
    with patch("agentic_traveler.analytics.metrics_tracker.record_token_usage") as mock_record:
        log_and_accumulate(
            agent_name="compaction",
            model_name="gemini-3.1-flash-lite",
            user_id="system",
            response=resp,
            latency_ms=250,
        )
        
        # Verify compaction directly records metrics
        mock_record.assert_called_once_with(
            agent_name="compaction",
            model_name="gemini-3.1-flash-lite",
            input_tokens=150,
            output_tokens=70,
            total_cost_credits=pytest.approx(1, abs=1)
        )


@patch("agentic_traveler.tools.db_client.get_db")
def test_save_and_finish_aggregates_usage_and_costs(mock_get_db):
    """_save_and_finish aggregates multiple small model calls in a turn to avoid overcharging."""
    mock_rpc = MagicMock()
    mock_get_db.return_value.rpc = mock_rpc
    
    # 2 small calls for gemini-3.1-flash-lite
    # Each call is 150 prompt + 70 candidates.
    # Individually, each would ceil to 1 credit.
    # Combined, 300 prompt + 140 candidates should still ceil to exactly 1 credit!
    token_records = [
        {
            "model_name": "gemini-3.1-flash-lite",
            "input_tokens": 150,
            "output_tokens": 70,
            "grounding_used": False,
            "grounding_cost_credits": 0,
        },
        {
            "model_name": "gemini-3.1-flash-lite",
            "input_tokens": 150,
            "output_tokens": 70,
            "grounding_used": False,
            "grounding_cost_credits": 0,
        }
    ]
    
    coordinator = MagicMock()
    user_doc = {"id": "test-uuid-123", "credits": {"balance": 100}}
    
    with patch("agentic_traveler.analytics.metrics_tracker.record_token_usage") as mock_record, \
         patch("agentic_traveler.analytics.usage_tracker._resolve_user_uuid", return_value="test-uuid-123"), \
         patch("agentic_traveler.economy.credit_manager.deduct_credits_async") as mock_deduct:
             
        _save_and_finish(
            coordinator=coordinator,
            user_doc=user_doc,
            user_id="test-uuid-123",
            message_text="Hi",
            response_text="Hello",
            telegram_user_id="user_tg_123",
            token_records=token_records,
            t_total=0.5,
        )
        
        # Verify total turn-level credit deduction is exactly 1 credit
        mock_deduct.assert_called_once_with("test-uuid-123", 1)
        
        # Verify weekly summary records the aggregated cost of 1 credit once for this model
        mock_record.assert_called_once_with(
            agent_name="orchestrator",
            model_name="gemini-3.1-flash-lite",
            input_tokens=300,
            output_tokens=140,
            total_cost_credits=1
        )
        
        # Verify Supabase RPC records the aggregated cost of 1 credit
        mock_rpc.assert_called_once_with("accumulate_user_usage", {
            "p_user_id": "test-uuid-123",
            "p_model_name": "gemini-3.1-flash-lite",
            "p_input_tokens": 300,
            "p_output_tokens": 140,
            "p_is_grounded": 0,
            "p_cost_credits": 1
        })
