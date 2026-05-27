"""
Shared utilities for orchestrator agents.
"""
from typing import Any
import logging
from agentic_traveler.tools.weather import WeatherService

logger = logging.getLogger(__name__)


def has_grounding(response: Any) -> bool:
    """Return True if Google Search grounding was used in the response."""
    try:
        for candidate in (getattr(response, "candidates", None) or []):
            meta = getattr(candidate, "grounding_metadata", None)
            if meta and getattr(meta, "grounding_chunks", None):
                return True
    except Exception:
        pass
    return False


def check_weather(location: str, days: int = 7) -> str:
    """
    Retrieves the weather forecast for a given location.

    Use only when the user has confirmed travel within the next 10 days
    (e.g. specific dates, "this weekend", "leaving Friday"). Do not call
    for discovery or destination questions with no confirmed near-future date.
    If only a region is given, infer a representative city.

    Args:
        location: Specific location string (e.g. "Kuta, Bali, Indonesia").
        days: Number of forecast days (default 7, max 10).

    Returns:
        Formatted weather summary.
    """
    logger.info("🔧 Shared tool: check_weather(location=%s, days=%d)", location, days)
    coords = WeatherService.get_coordinates(location)
    if not coords:
        return f"I couldn't find the location '{location}'. Could you be more specific?"
    weather_data = WeatherService.get_weather(coords["lat"], coords["lng"], days=min(days, 10))
    if not weather_data:
        return f"I'm having trouble fetching weather for {coords['name']} right now."
    full_name = f"{coords['name']}, {coords['country']}" if coords.get("country") else coords["name"]
    return WeatherService.format_weather_summary(full_name, weather_data)
