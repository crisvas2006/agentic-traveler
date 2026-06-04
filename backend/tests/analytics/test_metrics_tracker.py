"""Tests for the metrics_tracker module."""

from datetime import date
from unittest.mock import MagicMock, patch


def test_get_week_key_returns_sunday():
    from agentic_traveler.analytics.metrics_tracker import _get_week_key
    # Monday 2026-03-09 → Sunday 2026-03-15
    monday = date(2026, 3, 9)
    assert _get_week_key(monday) == "2026-03-15"

    # Thursday 2026-03-13 → same Sunday 2026-03-15
    thursday = date(2026, 3, 13)
    assert _get_week_key(thursday) == "2026-03-15"

    # Sunday 2026-03-15 → same Sunday 2026-03-15
    sunday = date(2026, 3, 15)
    assert _get_week_key(sunday) == "2026-03-15"

    # Monday 2026-03-16 → next Sunday 2026-03-22
    next_monday = date(2026, 3, 16)
    assert _get_week_key(next_monday) == "2026-03-22"


def test_record_interaction_accumulates():
    """Buffer should accumulate interactions without writing to Firestore."""
    import agentic_traveler.analytics.metrics_tracker as mt
    mt._reset_locked()  # start fresh

    mt.record_interaction(user_id="user1", is_new_user=True)
    mt.record_interaction(user_id="user2", is_new_user=False)

    assert mt._total_interactions == 2
    assert mt._new_users == 1
    assert mt._event_count == 2


def test_record_token_usage_accumulates():
    """Token rollup should accumulate per-model data including cost credits."""
    import agentic_traveler.analytics.metrics_tracker as mt
    mt._reset_locked()

    mt.record_token_usage(
        agent_name="orchestrator",
        model_name="gemini-2.5-flash",
        input_tokens=100,
        output_tokens=200,
        total_cost_credits=5,
    )
    mt.record_token_usage(
        agent_name="discovery",
        model_name="gemini-2.5-flash",
        input_tokens=50,
        output_tokens=80,
        total_cost_credits=3,
    )

    safe_model = "gemini-2_5-flash"
    assert mt._token_usage[safe_model]["input"] == 150
    assert mt._token_usage[safe_model]["output"] == 280
    assert mt._token_usage[safe_model]["call_count"] == 2
    assert mt._token_usage[safe_model]["total_cost_credits"] == 8
    assert mt._agent_calls["orchestrator"] == 1
    assert mt._agent_calls["discovery"] == 1


def test_flush_writes_correct_supabase_payload():
    """Flush should write a correctly shaped snapshot to Supabase."""
    import agentic_traveler.analytics.metrics_tracker as mt
    mt._reset_locked()

    mt.record_interaction(user_id="userA", is_new_user=True)
    mt.record_token_usage(
        agent_name="orchestrator",
        model_name="gemini-flash",
        input_tokens=10,
        output_tokens=20,
        total_cost_credits=1,
    )

    with patch("agentic_traveler.analytics.metrics_tracker._write_to_supabase") as mock_write:
        # manually trigger flush
        with mt._lock:
            mt._flush_locked()

    # The snapshot passed to _write_to_supabase should have the right shape
    assert mock_write.called
    snap = mock_write.call_args[0][0]
    assert snap["total_interactions"] == 1
    assert snap["new_users"] == 1
    assert "orchestrator" in snap["agent_calls"]
    assert snap["token_usage"]["gemini-flash"]["total_cost_credits"] == 1


def test_threshold_flush_triggers():
    """Buffer should auto-flush when FLUSH_THRESHOLD events are reached."""
    import agentic_traveler.analytics.metrics_tracker as mt
    mt._reset_locked()

    with patch.object(mt, "FLUSH_THRESHOLD", 3):
        with patch("agentic_traveler.analytics.metrics_tracker._write_to_supabase") as mock_write:
            mt.record_interaction(user_id="u1")
            mt.record_interaction(user_id="u2")
            # Third event should trigger flush
            mt.record_interaction(user_id="u3")

    assert mock_write.called  # flush happened
    # Buffer should be reset after flush
    assert mt._event_count == 0


@patch("agentic_traveler.tools.db_client.get_db")
def test_write_to_supabase_merges_credits(mock_get_db):
    """_write_to_supabase correctly merges existing DB values with weekly metrics snapshot."""
    from agentic_traveler.analytics.metrics_tracker import _write_to_supabase
    
    # 1. Setup mock database responses
    existing_row = {
        "week_ending": "2026-05-31",
        "total_interactions": 10,
        "new_users": 2,
        "agent_calls": {"orchestrator": 8},
        "token_usage": {
            "gemini-2_5-flash": {
                "input": 1000,
                "output": 500,
                "call_count": 5,
                "total_cost_credits": 15
            }
        },
        "total_cost_credits": 15,
        "promo_redeemed": {"PROMO1": 1},
        "grounding_calls": 1
    }
    
    # Mock chain: get_db().table().select().eq().maybe_single().execute()
    mock_execute = MagicMock()
    mock_execute.data = existing_row
    
    mock_maybe_single = MagicMock()
    mock_maybe_single.execute.return_value = mock_execute
    
    mock_eq = MagicMock()
    mock_eq.maybe_single.return_value = mock_maybe_single
    
    mock_select = MagicMock()
    mock_select.eq.return_value = mock_eq
    
    mock_upsert = MagicMock()
    mock_upsert.execute = MagicMock()
    
    mock_table = MagicMock()
    mock_table.select.return_value = mock_select
    mock_table.upsert.return_value = mock_upsert
    
    mock_get_db.return_value.table.return_value = mock_table
    
    # 2. Setup weekly metrics snapshot
    snapshot = {
        "total_interactions": 5,
        "new_users": 1,
        "agent_calls": {"orchestrator": 2, "discovery": 1},
        "token_usage": {
            "gemini-2_5-flash": {
                "input": 500,
                "output": 200,
                "call_count": 2,
                "total_cost_credits": 6
            },
            "gemini-3_5-flash": {
                "input": 300,
                "output": 100,
                "call_count": 1,
                "total_cost_credits": 20
            }
        },
        "promo_redeemed": {"PROMO2": 1},
        "grounding_calls": 2,
        "event_count": 10
    }
    
    # 3. Invoke function under test
    with patch("agentic_traveler.analytics.metrics_tracker._week_ending_key", return_value="2026-05-31"):
        _write_to_supabase(snapshot)
        
    # 4. Assert merging behavior
    mock_table.upsert.assert_called_once()
    merged_payload = mock_table.upsert.call_args[0][0]
    
    assert merged_payload["week_ending"] == "2026-05-31"
    assert merged_payload["total_interactions"] == 15
    assert merged_payload["new_users"] == 3
    assert merged_payload["agent_calls"] == {"orchestrator": 10, "discovery": 1}
    assert merged_payload["grounding_calls"] == 3
    
    # Check model-level merged costs
    model_usage = merged_payload["token_usage"]
    assert model_usage["gemini-2_5-flash"]["input"] == 1500
    assert model_usage["gemini-2_5-flash"]["output"] == 700
    assert model_usage["gemini-2_5-flash"]["call_count"] == 7
    assert model_usage["gemini-2_5-flash"]["total_cost_credits"] == 21
    
    assert model_usage["gemini-3_5-flash"]["input"] == 300
    assert model_usage["gemini-3_5-flash"]["output"] == 100
    assert model_usage["gemini-3_5-flash"]["call_count"] == 1
    assert model_usage["gemini-3_5-flash"]["total_cost_credits"] == 20
    
    # Check global accumulated weekly credits (15 existing + 6 flash + 20 flash-3.5 = 41 credits)
    assert merged_payload["total_cost_credits"] == 41
