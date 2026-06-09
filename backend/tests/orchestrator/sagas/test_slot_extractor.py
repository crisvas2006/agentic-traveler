"""Slot Extractor unit tests."""

from unittest.mock import MagicMock

from agentic_traveler.orchestrator.sagas.slot_extractor import extract_trip_slots

def test_extract_trip_slots_success():
    client = MagicMock()
    mock_response = MagicMock()
    mock_response.text = '{"destinations": ["Paris"], "pace": "slow", "structure": "loose"}'
    client.models.generate_content.return_value = mock_response
    
    res = extract_trip_slots(client, "I want to go to Paris with a slow pace")
    
    assert res["destinations"] == ["Paris"]
    assert res["pace"] == "slow"
    assert res["structure"] == "loose"

def test_extract_trip_slots_empty():
    client = MagicMock()
    mock_response = MagicMock()
    mock_response.text = '{}'
    client.models.generate_content.return_value = mock_response
    
    res = extract_trip_slots(client, "hello")
    assert res == {}

def test_extract_trip_slots_handles_malformed_json():
    client = MagicMock()
    mock_response = MagicMock()
    mock_response.text = 'not json'
    client.models.generate_content.return_value = mock_response
    
    res = extract_trip_slots(client, "hello")
    assert res == {}
