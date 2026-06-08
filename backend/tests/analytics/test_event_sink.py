from unittest.mock import MagicMock, patch
from agentic_traveler.analytics.event_sink import emit_metric_now, flush_metrics

@patch("agentic_traveler.analytics.event_sink.get_db")
def test_emit_metric_now_success(mock_get_db):
    mock_table = MagicMock()
    mock_insert = MagicMock()
    mock_get_db.return_value.table.return_value = mock_table
    mock_table.insert.return_value = mock_insert
    
    emit_metric_now("test_event", user_id="123", payload={"key": "value"})
    
    mock_get_db.return_value.table.assert_called_with("analytics_events")
    mock_table.insert.assert_called_with({
        "event_name": "test_event",
        "user_id": "123",
        "trip_id": None,
        "payload": {"key": "value"}
    })
    mock_insert.execute.assert_called_once()

@patch("agentic_traveler.analytics.event_sink.get_db")
def test_emit_metric_now_failure_handled(mock_get_db):
    mock_get_db.side_effect = Exception("DB error")
    
    # Should not raise exception
    emit_metric_now("test_event")

@patch("agentic_traveler.analytics.event_sink.get_db")
def test_flush_metrics_success(mock_get_db):
    mock_table = MagicMock()
    mock_insert = MagicMock()
    mock_get_db.return_value.table.return_value = mock_table
    mock_table.insert.return_value = mock_insert
    
    rows = [{"event_name": "event1"}, {"event_name": "event2"}]
    flush_metrics(rows)
    
    mock_get_db.return_value.table.assert_called_with("analytics_events")
    mock_table.insert.assert_called_with(rows)
    mock_insert.execute.assert_called_once()

@patch("agentic_traveler.analytics.event_sink.get_db")
def test_flush_metrics_empty(mock_get_db):
    flush_metrics([])
    mock_get_db.assert_not_called()

@patch("agentic_traveler.analytics.event_sink.get_db")
def test_flush_metrics_failure_handled(mock_get_db):
    mock_get_db.side_effect = Exception("DB error")
    
    # Should not raise exception
    flush_metrics([{"event_name": "event1"}])
