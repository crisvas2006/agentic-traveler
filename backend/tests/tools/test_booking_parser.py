from unittest.mock import MagicMock, patch

from agentic_traveler.tools.booking_parser import parse_booking

def test_parse_booking_success():
    with patch("agentic_traveler.tools.booking_parser.get_client") as mock_get_client:
        mock_client = MagicMock()
        mock_get_client.return_value = mock_client
        
        mock_response = MagicMock()
        mock_response.text = '{"booking_kind": "flight", "flight": {"airline": "Wizz Air", "number": "W6 1234", "from_": "LTN", "to": "BUD", "depart_local": "2026-12-15 11:25", "arrive_local": "2026-12-15 14:55", "confirmation_code": "ABC123", "notes": null}, "confidence": 0.95}'
        mock_client.models.generate_content.return_value = mock_response

        extraction, _ = parse_booking("Booking: Wizz Air flight W6 1234 from LTN to BUD on Dec 15 11:25. PNR: ABC123")
        
        assert extraction.booking_kind == "flight"
        assert extraction.flight is not None
        assert extraction.flight.airline == "Wizz Air"
        assert extraction.flight.confirmation_code == "ABC123"
        assert extraction.confidence == 0.95

def test_parse_booking_low_confidence_fallback():
    with patch("agentic_traveler.tools.booking_parser.get_client") as mock_get_client:
        mock_client = MagicMock()
        mock_get_client.return_value = mock_client
        
        # Simulate a validation error by making the mock return invalid JSON
        mock_response = MagicMock()
        mock_response.text = '{"invalid_json": true'
        mock_client.models.generate_content.return_value = mock_response

        extraction, _ = parse_booking("GARBAGE TEXT")
        
        assert extraction.confidence == 0.0
        assert extraction.booking_kind == "activity"
        assert "GARBAGE TEXT" in extraction.fallback_notes
