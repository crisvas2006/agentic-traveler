"""Batched writer to analytics_events. One INSERT per turn, never per event.

The orchestrator's EventEmitter buffers events during a turn; this module
flushes them at the end. emit_metric_now() exists for callers that need
immediate persistence (rare — e.g., signup_completed at registration time).
"""

import logging
from typing import Any
from agentic_traveler.tools.db_client import get_db

logger = logging.getLogger(__name__)


def emit_metric_now(event_name: str,
                    *,
                    user_id: str | None = None,
                    trip_id: str | None = None,
                    payload: dict[str, Any] | None = None) -> None:
    """Synchronous, single-event write. Use sparingly — prefer batched."""
    try:
        get_db().table("analytics_events").insert({
            "event_name": event_name,
            "user_id": user_id,
            "trip_id": trip_id,
            "payload": payload or {},
        }).execute()
    except Exception:
        logger.warning("emit_metric_now failed; dropping event.", exc_info=True)


def flush_metrics(rows: list[dict[str, Any]]) -> None:
    """Batched insert of accumulated events. Drops on failure (analytics
    must never break a user turn). Called by the orchestrator at end of turn."""
    if not rows:
        return
    try:
        get_db().table("analytics_events").insert(rows).execute()
    except Exception:
        logger.warning(
            "flush_metrics failed for %d rows; dropping.", len(rows), exc_info=True
        )
