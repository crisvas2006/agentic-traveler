"""
Unit tests for EventEmitter (Task 35).

Covers: metric buffering, flush, status/delta routing, type alignment,
        failure isolation, and idempotency of flush.

No Supabase / Gemini calls — pure unit tests.
"""

from unittest.mock import MagicMock, patch

from agentic_traveler.orchestrator.event_emitter import EventEmitter


# ---------------------------------------------------------------------------
# Metric buffering and flush
# ---------------------------------------------------------------------------

def test_metric_emit_buffers_row():
    """emit("metric", ...) appends one row to the internal buffer."""
    ee = EventEmitter(user_id="u1", trip_id="t1")
    ee.emit("metric", {"name": "turn_completed", "latency_ms": 500})
    assert len(ee._metric_buffer) == 1
    row = ee._metric_buffer[0]
    assert row["event_name"] == "turn_completed"
    assert row["user_id"] == "u1"
    assert row["trip_id"] == "t1"
    # "name" must be stripped from the payload sent to the DB
    assert "name" not in row["payload"]
    assert row["payload"]["latency_ms"] == 500


def test_metric_emit_multiple_rows():
    """Multiple emit("metric") calls accumulate all rows."""
    ee = EventEmitter(user_id="u1", trip_id=None)
    ee.emit("metric", {"name": "saga_entered"})
    ee.emit("metric", {"name": "tool_invoked", "tool": "check_weather"})
    ee.emit("metric", {"name": "turn_completed"})
    assert len(ee._metric_buffer) == 3


def test_flush_metrics_calls_sink_with_all_rows():
    """flush_metrics() sends all buffered rows in one batched insert."""
    ee = EventEmitter(user_id="u1", trip_id=None)
    ee.emit("metric", {"name": "saga_entered"})
    ee.emit("metric", {"name": "turn_completed", "latency_ms": 300})

    with patch("agentic_traveler.orchestrator.event_emitter.flush_metrics") as mock_flush:
        ee.flush_metrics()

    mock_flush.assert_called_once()
    rows = mock_flush.call_args[0][0]
    assert len(rows) == 2
    assert rows[0]["event_name"] == "saga_entered"
    assert rows[1]["event_name"] == "turn_completed"


def test_flush_clears_buffer():
    """After flush_metrics(), the buffer is empty; a second flush is a no-op."""
    ee = EventEmitter(user_id="u1", trip_id=None)
    ee.emit("metric", {"name": "turn_completed"})

    with patch("agentic_traveler.orchestrator.event_emitter.flush_metrics") as mock_flush:
        ee.flush_metrics()
        ee.flush_metrics()  # second call — buffer is empty

    # flush_metrics(sink) called exactly once (not twice)
    mock_flush.assert_called_once()


def test_flush_empty_buffer_does_not_call_sink():
    """flush_metrics() with an empty buffer never touches the DB."""
    ee = EventEmitter(user_id="u1", trip_id=None)
    with patch("agentic_traveler.orchestrator.event_emitter.flush_metrics") as mock_flush:
        ee.flush_metrics()
    mock_flush.assert_not_called()


def test_metric_unnamed_fallback():
    """emit("metric", {}) falls back event_name to "unnamed"."""
    ee = EventEmitter(user_id=None, trip_id=None)
    ee.emit("metric", {})
    assert ee._metric_buffer[0]["event_name"] == "unnamed"


# ---------------------------------------------------------------------------
# Status routing
# ---------------------------------------------------------------------------

def test_status_emit_calls_on_status_with_payload_dict():
    """emit("status", payload) passes the full payload dict to on_status (Task 37)."""
    on_status = MagicMock()
    ee = EventEmitter(user_id=None, trip_id=None, on_status=on_status)
    payload = {"phase": "tool", "text": "Searching the web..."}
    ee.emit("status", payload)
    on_status.assert_called_once_with(payload)


def test_status_emit_empty_payload_is_passed_through():
    """emit("status", {}) passes the empty dict — never raises."""
    on_status = MagicMock()
    ee = EventEmitter(user_id=None, trip_id=None, on_status=on_status)
    ee.emit("status", {})
    on_status.assert_called_once_with({})


def test_status_emit_no_callback_is_silent():
    """emit("status", ...) with no on_status registered is a no-op."""
    ee = EventEmitter(user_id=None, trip_id=None)  # no on_status
    ee.emit("status", {"message": "Thinking..."})  # must not raise


def test_status_callback_exception_is_swallowed():
    """If on_status raises, EventEmitter logs and continues — never re-raises."""
    on_status = MagicMock(side_effect=RuntimeError("SSE broken"))
    ee = EventEmitter(user_id=None, trip_id=None, on_status=on_status)
    ee.emit("status", {"message": "hi"})  # must not propagate


# ---------------------------------------------------------------------------
# Delta routing
# ---------------------------------------------------------------------------

def test_delta_emit_calls_on_delta_with_payload_dict():
    """emit("delta", {"text": "token"}) passes the full payload dict to on_delta."""
    on_delta = MagicMock()
    ee = EventEmitter(user_id=None, trip_id=None, on_delta=on_delta)
    payload = {"text": "partial answer"}
    ee.emit("delta", payload)
    on_delta.assert_called_once_with(payload)


def test_delta_callback_exception_is_swallowed():
    on_delta = MagicMock(side_effect=RuntimeError("stream error"))
    ee = EventEmitter(user_id=None, trip_id=None, on_delta=on_delta)
    ee.emit("delta", {"text": "chunk"})  # must not propagate


# ---------------------------------------------------------------------------
# Unknown phase
# ---------------------------------------------------------------------------

def test_unknown_phase_is_dropped_silently():
    """emit() with an unrecognised phase drops the event without raising."""
    ee = EventEmitter(user_id=None, trip_id=None)
    ee.emit("unsupported_phase", {"foo": "bar"})  # must not raise
    assert len(ee._metric_buffer) == 0
