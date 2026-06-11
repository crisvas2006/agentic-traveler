import logging
import threading
import time
from datetime import datetime, timezone
from typing import Optional

import httpx

logger = logging.getLogger(__name__)

# Nominatim strictly requires <= 1 request per second
_RATE_LIMIT_INTERVAL_SEC = 1.1

# Global lock to serialize geocoding calls across the same process worker.
_geocode_lock = threading.Lock()
_last_call_time: float = 0.0

# Using a generic admin email or environment variable if available
_USER_AGENT = "AletheiaTravel/1.0"


def _rate_limit_sleep():
    global _last_call_time
    now = time.time()
    elapsed = now - _last_call_time
    if elapsed < _RATE_LIMIT_INTERVAL_SEC:
        time.sleep(_RATE_LIMIT_INTERVAL_SEC - elapsed)
    _last_call_time = time.time()


def _fetch_geocode(name: str) -> Optional[dict]:
    url = "https://nominatim.openstreetmap.org/search"
    params = {
        "q": name,
        "format": "jsonv2",
        "limit": 1
    }
    headers = {
        "User-Agent": _USER_AGENT
    }

    try:
        with httpx.Client() as client:
            # 5s timeout, single retry on timeout/5xx
            for attempt in range(2):
                try:
                    response = client.get(url, params=params, headers=headers, timeout=5.0)
                    response.raise_for_status()
                    data = response.json()
                    return data
                except httpx.HTTPStatusError as e:
                    if e.response.status_code >= 500 and attempt == 0:
                        logger.warning(f"Nominatim 5xx error, retrying: {e}")
                        time.sleep(2.0)
                        continue
                    else:
                        logger.warning(f"Nominatim HTTP error {e.response.status_code}: {e}")
                        return None
                except httpx.RequestError as e:
                    if attempt == 0:
                        logger.warning(f"Nominatim request error, retrying: {e}")
                        time.sleep(2.0)
                        continue
                    else:
                        logger.warning(f"Nominatim request error (final): {e}")
                        return None
                except Exception as e:
                    logger.warning(f"Nominatim unexpected error: {e}")
                    return None
            return None
    except Exception as e:
        logger.exception(f"Fatal error in geocoder client: {e}")
        return None


def geocode_destination(name: str) -> Optional[dict]:
    """One Nominatim /search call (format=jsonv2, limit=1).
    Returns {"lat": float, "lng": float, "bbox": [s, n, w, e],
    "display_name": str, "geocoded_at": iso} or None on any failure.
    Policy: User-Agent "AletheiaTravel/1.0",
    module-level lock + min-interval 1.1s between calls, timeout 5s,
    single retry with backoff on 5xx/timeout. Never raises.
    """
    if not name or not name.strip():
        return None

    from agentic_traveler.analytics import emit_metric_now

    logger.info(f"Geocoding destination: {name}")
    emit_metric_now("tool_invoked", payload={
        "tool": "geocode_destination",
        "name": name
    })
    
    with _geocode_lock:
        _rate_limit_sleep()
        start_time = time.time()
        
        data = _fetch_geocode(name)
        
        latency = time.time() - start_time
        logger.debug(f"Geocode latency: {latency:.2f}s")
        
        if not data or len(data) == 0:
            logger.warning(f"Nominatim returned no results for: {name}")
            emit_metric_now("tool_failed", payload={
                "tool": "geocode_destination",
                "latency_ms": int(latency * 1000),
                "reason": "no_results"
            })
            return None

        result = data[0]
        try:
            # Nominatim format: "boundingbox": ["lat_min", "lat_max", "lon_min", "lon_max"]
            # We want [s, n, w, e] -> [lat_min, lat_max, lon_min, lon_max]
            bbox = [float(x) for x in result.get("boundingbox", [])]
            if len(bbox) != 4:
                bbox = None
                
            coords = {
                "lat": float(result["lat"]),
                "lng": float(result["lon"]),
                "bbox": bbox,
                "display_name": result.get("display_name", ""),
                "geocoded_at": datetime.now(timezone.utc).isoformat(),
                "source_name": name
            }
            logger.info(f"Geocoded '{name}' to {coords['lat']}, {coords['lng']}")
            emit_metric_now("tool_succeeded", payload={
                "tool": "geocode_destination",
                "latency_ms": int(latency * 1000)
            })
            return coords
        except (KeyError, ValueError, TypeError) as e:
            logger.warning(f"Failed to parse Nominatim result for {name}: {e}")
            emit_metric_now("tool_failed", payload={
                "tool": "geocode_destination",
                "latency_ms": int(latency * 1000),
                "reason": f"parse_error: {str(e)}"
            })
            return None
