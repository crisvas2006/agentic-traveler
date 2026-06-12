from unittest import mock
from httpx import Response
from agentic_traveler.tools.geocoder import geocode_destination

@mock.patch("agentic_traveler.tools.geocoder.httpx.Client")
def test_geocode_destination_success(mock_client_class):
    mock_client = mock.MagicMock()
    mock_client_class.return_value.__enter__.return_value = mock_client
    
    mock_response = mock.MagicMock(spec=Response)
    mock_response.json.return_value = [{
        "lat": "35.0116",
        "lon": "135.7681",
        "boundingbox": ["34.873", "35.321", "135.555", "135.878"],
        "display_name": "Kyoto, Japan"
    }]
    mock_response.raise_for_status.return_value = None
    mock_client.get.return_value = mock_response

    # Need to patch _rate_limit_sleep to speed up tests
    with mock.patch("agentic_traveler.tools.geocoder._rate_limit_sleep"):
        result = geocode_destination("Kyoto")
        
    assert result is not None
    assert result["lat"] == 35.0116
    assert result["lng"] == 135.7681
    assert result["bbox"] == [34.873, 35.321, 135.555, 135.878]
    assert result["display_name"] == "Kyoto, Japan"
    assert result["source_name"] == "Kyoto"
    assert "geocoded_at" in result

@mock.patch("agentic_traveler.tools.geocoder.httpx.Client")
def test_geocode_destination_no_results(mock_client_class):
    mock_client = mock.MagicMock()
    mock_client_class.return_value.__enter__.return_value = mock_client
    
    mock_response = mock.MagicMock(spec=Response)
    mock_response.json.return_value = []
    mock_response.raise_for_status.return_value = None
    mock_client.get.return_value = mock_response

    with mock.patch("agentic_traveler.tools.geocoder._rate_limit_sleep"):
        result = geocode_destination("NonExistentCity12345")
        
    assert result is None

def test_geocode_empty():
    assert geocode_destination("") is None
    assert geocode_destination("   ") is None
