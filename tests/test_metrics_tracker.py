"""Tests for the metrics_tracker module."""

from datetime import date
from unittest.mock import MagicMock, patch, call


def test_get_week_key_returns_sunday():
    from agentic_traveler.metrics_tracker import _get_week_key
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
    import agentic_traveler.metrics_tracker as mt
    mt._reset_locked()  # start fresh

    mt.record_interaction(user_id="user1", is_new_user=True)
    mt.record_interaction(user_id="user2", is_new_user=False)

    assert mt._total_interactions == 2
    assert mt._new_users == 1
    assert "user1" in mt._active_users
    assert "user2" in mt._active_users
    assert mt._event_count == 2


def test_record_token_usage_accumulates():
    """Token rollup should accumulate per-model data."""
    import agentic_traveler.metrics_tracker as mt
    mt._reset_locked()

    mt.record_token_usage(
        agent_name="orchestrator",
        model_name="gemini-2.5-flash",
        input_tokens=100,
        output_tokens=200,
    )
    mt.record_token_usage(
        agent_name="discovery",
        model_name="gemini-2.5-flash",
        input_tokens=50,
        output_tokens=80,
    )

    safe_model = "gemini-2_5-flash"
    assert mt._token_usage[safe_model]["total_input_tokens"] == 150
    assert mt._token_usage[safe_model]["total_output_tokens"] == 280
    assert mt._token_usage[safe_model]["call_count"] == 2
    assert mt._agent_calls["orchestrator"] == 1
    assert mt._agent_calls["discovery"] == 1


def test_flush_writes_correct_firestore_paths():
    """Flush should write atomic increments to the correct collection/document."""
    import agentic_traveler.metrics_tracker as mt
    mt._reset_locked()

    mt.record_interaction(user_id="userA", is_new_user=True)
    mt.record_token_usage(
        agent_name="orchestrator",
        model_name="gemini-flash",
        input_tokens=10,
        output_tokens=20,
    )

    with patch("agentic_traveler.metrics_tracker._write_to_firestore") as mock_write:
        # manually trigger flush
        with mt._lock:
            mt._flush_locked()

    # The snapshot passed to _write_to_firestore should have the right shape
    # (_write_to_firestore is called in a thread, but since we patched it, it
    # runs synchronously here)
    assert mock_write.called
    snap = mock_write.call_args[0][0]
    assert snap["total_interactions"] == 1
    assert snap["new_users"] == 1
    assert "userA" in snap["active_users"]
    assert "orchestrator" in snap["agent_calls"]


def test_threshold_flush_triggers():
    """Buffer should auto-flush when FLUSH_THRESHOLD events are reached."""
    import agentic_traveler.metrics_tracker as mt
    mt._reset_locked()

    with patch.object(mt, "FLUSH_THRESHOLD", 3):
        with patch("agentic_traveler.metrics_tracker._write_to_firestore") as mock_write:
            mt.record_interaction(user_id="u1")
            mt.record_interaction(user_id="u2")
            # Third event should trigger flush
            mt.record_interaction(user_id="u3")

    assert mock_write.called  # flush happened
    # Buffer should be reset after flush
    assert mt._event_count == 0
