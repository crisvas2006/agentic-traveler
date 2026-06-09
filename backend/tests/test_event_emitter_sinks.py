"""EventEmitter sink routing (Task 37).

Verifies each phase reaches the right sink with the right shape, that metric
events are buffered (not sent to status/delta sinks), and that a failing
status/delta sink never breaks the turn. No DB / LLM.
"""

from unittest.mock import MagicMock, patch

from agentic_traveler.orchestrator.event_emitter import EventEmitter


def test_status_routes_only_to_on_status():
    on_status, on_delta = MagicMock(), MagicMock()
    ee = EventEmitter(user_id="u1", trip_id="t1", on_status=on_status, on_delta=on_delta)
    payload = {"phase": "router", "text": "Understanding…"}
    ee.emit("status", payload)
    on_status.assert_called_once_with(payload)
    on_delta.assert_not_called()
    assert len(ee._metric_buffer) == 0


def test_delta_routes_only_to_on_delta():
    on_status, on_delta = MagicMock(), MagicMock()
    ee = EventEmitter(user_id="u1", trip_id="t1", on_status=on_status, on_delta=on_delta)
    payload = {"text": "Iceland in late Jan "}
    ee.emit("delta", payload)
    on_delta.assert_called_once_with(payload)
    on_status.assert_not_called()
    assert len(ee._metric_buffer) == 0


def test_metric_does_not_touch_status_or_delta_sinks():
    on_status, on_delta = MagicMock(), MagicMock()
    ee = EventEmitter(user_id="u1", trip_id="t1", on_status=on_status, on_delta=on_delta)
    ee.emit("metric", {"name": "turn_completed", "latency_ms": 10})
    on_status.assert_not_called()
    on_delta.assert_not_called()
    assert len(ee._metric_buffer) == 1
    assert ee._metric_buffer[0]["event_name"] == "turn_completed"


def test_status_sink_exception_is_swallowed():
    on_status = MagicMock(side_effect=RuntimeError("SSE writer closed"))
    ee = EventEmitter(user_id="u1", trip_id=None, on_status=on_status)
    # Must not propagate — a dead client must never break the turn.
    ee.emit("status", {"phase": "router", "text": "x"})


def test_delta_sink_exception_is_swallowed():
    on_delta = MagicMock(side_effect=RuntimeError("client gone"))
    ee = EventEmitter(user_id="u1", trip_id=None, on_delta=on_delta)
    ee.emit("delta", {"text": "x"})


def test_no_sinks_is_silent_but_metrics_still_buffer():
    ee = EventEmitter(user_id="u1", trip_id=None)  # non-streaming path
    ee.emit("status", {"phase": "router", "text": "x"})  # no-op
    ee.emit("delta", {"text": "y"})                       # no-op
    ee.emit("metric", {"name": "saga_entered"})
    assert len(ee._metric_buffer) == 1


def test_flush_sends_buffer_to_sink_once():
    ee = EventEmitter(user_id="u1", trip_id=None)
    ee.emit("metric", {"name": "a"})
    ee.emit("metric", {"name": "b"})
    with patch("agentic_traveler.orchestrator.event_emitter.flush_metrics") as mock_flush:
        ee.flush_metrics()
        ee.flush_metrics()  # buffer now empty → no second sink call
    mock_flush.assert_called_once()
    assert len(mock_flush.call_args[0][0]) == 2
