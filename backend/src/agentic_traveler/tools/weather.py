import requests
import logging
from typing import Optional, Dict, Any

logger = logging.getLogger(__name__)

class WeatherService:
    """
    A service to interact with Open-Meteo APIs for geocoding and weather data.
    """
    GEOCODING_API = "https://geocoding-api.open-meteo.com/v1/search"
    WEATHER_API = "https://api.open-meteo.com/v1/forecast"

    @classmethod
    def get_coordinates(cls, location: str) -> Optional[Dict[str, Any]]:
        """
        Convert a location name to latitude and longitude.
        Handles "City, Region, Country" by fetching multiple results 
        and performing robust fuzzy matching on administrative levels.
        """
        try:
            # The API may fail on exact matches for detailed strings (e.g., "Kuta, Lombok, Indonesia")
            # so we query with "City, Country" to get better initial results for local disambiguation.
            if "," in location:
                parts = [p.strip() for p in location.split(",")]
                if len(parts) >= 3:
                    # Usually: City, Region, Country
                    search_name = f"{parts[0]}, {parts[-1]}"
                else:
                    search_name = location
            else:
                search_name = location
            
            logger.info(f"WeatherService: Querying geocoding API for search_name='{search_name}' (original: '{location}')")
            resp = requests.get(cls.GEOCODING_API, params={"name": search_name, "count": 10}, timeout=10)
            resp.raise_for_status()
            data = resp.json()
            results = data.get("results")
            if not results:
                logger.warning(f"No coordinates found for location: {location} (search_name: '{search_name}')")
                return None
            
            # 1. Start with the first result as a baseline
            best_match = results[0]
            
            # 2. If the user provided multiple parts (City, Island, Country), 
            # find the result that matches the most descriptive tokens.
            if "," in location:
                tokens = [t.strip().lower() for t in location.split(",")]
                city_token = tokens[0]
                region_tokens = tokens[1:]
                
                max_score = -1
                for res in results:
                    res_name = (res.get("name") or "").lower()
                    res_country = (res.get("country") or "").lower()
                    res_admin1 = (res.get("admin1") or "").lower()
                    res_admin2 = (res.get("admin2") or "").lower()
                    
                    score = 0
                    # Does the primary city match? (Partial match allowed for Kuta/Kute)
                    if city_token in res_name or res_name in city_token:
                        score += 5
                    
                    # How many extra regions/countries match?
                    for rt in region_tokens:
                        if rt in res_country or rt in res_admin1 or rt in res_admin2:
                            score += 10 # Region/Island matches are high weight
                    
                    if score > max_score:
                        max_score = score
                        best_match = res
                        # If we found a perfect match for BOTH city and a region, we're likely done
                        if score >= 15:
                            break

            return {
                "lat": best_match["latitude"],
                "lng": best_match["longitude"],
                "name": best_name if (best_name := best_match.get("name")) else location,
                "country": best_match.get("country", ""),
                "admin1": best_match.get("admin1", ""),
                "admin2": best_match.get("admin2", "")
            }
        except Exception as e:
            logger.error(f"Error fetching coordinates for {location}: {e}")
            return None

    @classmethod
    def get_weather(cls, lat: float, lng: float, days: int = 7) -> Optional[Dict[str, Any]]:
        """
        Fetch weather forecast for the given coordinates and number of days.
        """
        try:
            params = {
                "latitude": lat,
                "longitude": lng,
                "daily": "weather_code,temperature_2m_max,temperature_2m_min,precipitation_sum",
                "timezone": "auto",
                "forecast_days": days
            }
            resp = requests.get(cls.WEATHER_API, params=params, timeout=10)
            resp.raise_for_status()
            return resp.json()
        except Exception as e:
            logger.error(f"Error fetching weather for ({lat}, {lng}): {e}")
            return None

    @classmethod
    def format_weather_summary(cls, location_name: str, weather_data: Dict[str, Any]) -> str:
        """
        Format weather data into a human-readable summary.
        """
        daily = weather_data.get("daily", {})
        if not daily:
            return f"Sorry, I couldn't get the weather details for {location_name}."

        times = daily.get("time", [])
        max_temps = daily.get("temperature_2m_max", [])
        min_temps = daily.get("temperature_2m_min", [])
        codes = daily.get("weather_code", [])

        summary = f"<raw_weather_data location=\"{location_name}\">\n"
        summary += "CRITICAL INSTRUCTION: This is raw data for context. DO NOT output this list directly to the user. Synthesize it naturally into your conversational response (e.g. 'It will be mostly sunny and warm all week with a chance of rain on Friday.').\n"
        # Limit to 10 days max for the data block
        for i in range(min(len(times), 10)):
            date = times[i]
            t_max = max_temps[i]
            t_min = min_temps[i]
            condition = cls._get_condition_description(codes[i])
            summary += f"- {date}: {condition} ({t_min}C to {t_max}C)\n"
        summary += "</raw_weather_data>\n"
        
        return summary

    @staticmethod
    def _get_condition_description(code: int) -> str:
        """
        Map WMO weather codes to simple descriptions.
        """
        mapping = {
            0: "Clear sky",
            1: "Mainly clear", 2: "Partly cloudy", 3: "Overcast",
            45: "Fog", 48: "Depositing rime fog",
            51: "Drizzle: Light", 53: "Drizzle: Moderate", 55: "Drizzle: Dense intensity",
            56: "Freezing Drizzle: Light", 57: "Freezing Drizzle: Dense intensity",
            61: "Rain: Slight", 63: "Rain: Moderate", 65: "Rain: Heavy intensity",
            66: "Freezing Rain: Light", 67: "Freezing Rain: Heavy intensity",
            71: "Snow fall: Slight", 73: "Snow fall: Moderate", 75: "Snow fall: Heavy intensity",
            77: "Snow grains",
            80: "Rain showers: Slight", 81: "Rain showers: Moderate", 82: "Rain showers: Violent",
            85: "Snow showers: Slight", 86: "Snow showers: Heavy",
            95: "Thunderstorm: Slight or moderate", 96: "Thunderstorm with slight hail", 99: "Thunderstorm with heavy hail"
        }
        return mapping.get(code, "Unknown")
