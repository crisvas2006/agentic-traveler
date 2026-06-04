from unittest.mock import patch
from agentic_traveler.orchestrator.utils import check_weather

def test_check_weather_execution():
    """Verify the implementation of the check_weather helper function."""
    with patch("agentic_traveler.orchestrator.utils.WeatherService") as mock_weather_service:
        mock_weather_service.get_coordinates.return_value = {
            "lat": 51.5, "lng": -0.1, "name": "London", "country": "UK"
        }
        mock_weather_service.get_weather.return_value = {"daily": {"time": ["2026-03-08"]}}
        mock_weather_service.format_weather_summary.return_value = "Cloudy with a chance of meatballs"
        
        result = check_weather("London")
        
        mock_weather_service.get_coordinates.assert_called_once_with("London")
        mock_weather_service.get_weather.assert_called_once()
        assert "Cloudy with a chance of meatballs" in result

def test_check_weather_unknown_location():
    """Verify handling of unknown locations in check_weather helper function."""
    with patch("agentic_traveler.orchestrator.utils.WeatherService") as mock_weather_service:
        mock_weather_service.get_coordinates.return_value = None
        
        result = check_weather("Atlantis")
        assert "couldn't find the location" in result
