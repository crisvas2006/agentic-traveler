import pytest
from unittest.mock import patch, MagicMock
from agentic_traveler.tools.weather import WeatherService

class TestWeatherService:

    @patch("requests.get")
    def test_get_coordinates_success(self, mock_get):
        mock_resp = MagicMock()
        mock_resp.json.return_value = {
            "results": [
                {"latitude": 52.52, "longitude": 13.41, "name": "Berlin", "country": "Germany"}
            ]
        }
        mock_get.return_value = mock_resp

        coords = WeatherService.get_coordinates("Berlin")
        assert coords == {
            "lat": 52.52,
            "lng": 13.41,
            "name": "Berlin",
            "country": "Germany",
            "admin1": "",
            "admin2": ""
        }

    @patch("requests.get")
    def test_get_coordinates_no_results(self, mock_get):
        mock_resp = MagicMock()
        mock_resp.json.return_value = {"results": []}
        mock_get.return_value = mock_resp

        coords = WeatherService.get_coordinates("UnknownCity")
        assert coords is None

    @patch("requests.get")
    def test_get_coordinates_error(self, mock_get):
        mock_get.side_effect = Exception("API Down")
        coords = WeatherService.get_coordinates("Berlin")
        assert coords is None

    @patch("requests.get")
    def test_get_coordinates_ambiguous_disambiguation(self, mock_get):
        # Mocking a response where "Kute" (wrong) is rank 0 and "Kuta" (correct) is rank 1
        mock_resp = MagicMock()
        mock_resp.json.return_value = {
            "results": [
                {
                    "latitude": -8.892, 
                    "longitude": 116.248, 
                    "name": "Kute", 
                    "country": "Indonesia", 
                    "admin1": "West Nusa Tenggara",
                    "admin2": "Central Lombok Regency"
                },
                {
                    "latitude": -8.723, 
                    "longitude": 115.171, 
                    "name": "Kuta", 
                    "country": "Indonesia", 
                    "admin1": "Bali",
                    "admin2": "Badung Regency"
                }
            ]
        }
        mock_get.return_value = mock_resp

        # Searching for "Kuta, Bali" should skip "Kute" and pick "Kuta"
        coords = WeatherService.get_coordinates("Kuta, Bali")
        assert coords["name"] == "Kuta"
        assert coords["lat"] == -8.723
        
        # Searching for "Kuta, Bali" should pick "Kuta" (Bali)
        coords = WeatherService.get_coordinates("Kuta, Bali")
        assert coords["name"] == "Kuta"
        assert coords["admin1"] == "Bali"
        
        # Searching for "Kuta, Lombok" should pick "Kute" (West Nusa Tenggara)
        coords = WeatherService.get_coordinates("Kuta, Lombok")
        assert coords["name"] == "Kute"
        assert coords["admin1"] == "West Nusa Tenggara"

    @patch("requests.get")
    def test_get_weather_success(self, mock_get):
        mock_resp = MagicMock()
        mock_resp.json.return_value = {
            "daily": {
                "time": ["2026-03-08"],
                "temperature_2m_max": [20.0],
                "temperature_2m_min": [10.0],
                "weather_code": [0]
            }
        }
        mock_get.return_value = mock_resp

        weather = WeatherService.get_weather(52.52, 13.41, days=1)
        assert weather["daily"]["time"] == ["2026-03-08"]
        assert weather["daily"]["temperature_2m_max"] == [20.0]

    def test_format_weather_summary(self):
        weather_data = {
            "daily": {
                "time": ["2026-03-08", "2026-03-09"],
                "temperature_2m_max": [20.0, 18.0],
                "temperature_2m_min": [10.0, 9.0],
                "weather_code": [0, 3]
            }
        }
        summary = WeatherService.format_weather_summary("Berlin", weather_data)
        assert '<raw_weather_data location="Berlin">' in summary
        assert "CRITICAL INSTRUCTION" in summary
        assert "- 2026-03-08: Clear sky (10.0C to 20.0C)" in summary
        assert "- 2026-03-09: Overcast (9.0C to 18.0C)" in summary
        assert "</raw_weather_data>" in summary

    def test_format_weather_summary_no_data(self):
        summary = WeatherService.format_weather_summary("Berlin", {})
        assert "couldn't get the weather details" in summary
