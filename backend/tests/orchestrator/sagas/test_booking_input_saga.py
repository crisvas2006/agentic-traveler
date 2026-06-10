from unittest.mock import MagicMock, patch

from agentic_traveler.orchestrator.sagas.booking_input import BookingInputSaga

def test_booking_input_saga_should_activate():
    saga = BookingInputSaga()
    
    # Activates on booking_shaped entity
    can_act, wants_owner = saga.should_activate("CHAT", {"booking_shaped": True}, None, {})
    assert can_act and wants_owner
    
    # Activates on pending state
    can_act, wants_owner = saga.should_activate("CHAT", {}, None, {"pending_booking_extraction": {"some": "data"}})
    assert can_act and wants_owner
    
    # Doesn't activate otherwise
    can_act, wants_owner = saga.should_activate("CHAT", {}, None, {})
    assert not can_act

@patch("agentic_traveler.orchestrator.sagas.booking_input.parse_booking")
def test_booking_input_saga_run_turn_1(mock_parse):
    saga = BookingInputSaga()
    events = MagicMock()
    
    extraction = MagicMock()
    extraction.confidence = 0.9
    extraction.booking_kind = "flight"
    extraction.model_dump.return_value = {"booking_kind": "flight", "flight": {"airline": "LH", "number": "123", "from_": "MUC", "to": "KIX"}}
    mock_parse.return_value = (extraction, MagicMock())
    
    result = saga.run("PNR 123456", {"id": "u1"}, None, {}, [], events)
    
    assert "Found flight: LH 123 MUC" in result.text
    assert result.state_delta["pending_booking_extraction"] == extraction.model_dump()
    assert result.slot_request.slot == "booking_confirm"

@patch("agentic_traveler.tools.trip_repo.TripRepository")
def test_booking_input_saga_run_turn_2_confirm(mock_repo_class):
    saga = BookingInputSaga()
    events = MagicMock()
    mock_repo = MagicMock()
    mock_repo_class.return_value = mock_repo
    
    pending = {"booking_kind": "flight", "flight": {"airline": "LH", "number": "123", "datetime_local": "2026-10-10T10:00:00"}}
    
    result = saga.run("Yes", {"id": "u1"}, {"id": "t1"}, {"pending_booking_extraction": pending}, [], events)
    
    assert "Added to your trip" in result.text
    assert result.state_delta["pending_booking_extraction"] is None
    mock_repo.upsert_booking.assert_called_once()
    
def test_booking_input_saga_run_turn_2_reject():
    saga = BookingInputSaga()
    events = MagicMock()
    
    pending = {"booking_kind": "flight"}
    
    result = saga.run("No", {"id": "u1"}, {"id": "t1"}, {"pending_booking_extraction": pending}, [], events)
    
    assert "Okay, I won't save" in result.text
    assert result.state_delta["pending_booking_extraction"] is None
