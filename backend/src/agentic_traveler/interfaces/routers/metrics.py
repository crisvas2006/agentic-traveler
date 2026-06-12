"""Web client metric ingestion (Task 50).

The browser cannot write to analytics_events directly (no service key on the
client). This endpoint lets the web client record a small, ALLOWLISTED set of UI
events (the capability surface) through the same analytics_events path the
orchestrator uses. Auth via Supabase JWT; the event name is allowlisted so the
endpoint can't be used to write arbitrary rows.
"""

import logging

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field

from agentic_traveler.analytics.event_sink import emit_metric_now
from agentic_traveler.interfaces.dependencies import WebUserCtx, verify_supabase_jwt

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/metrics", tags=["Metrics"])

# Only these client-originated event names are accepted (trust boundary).
_ALLOWED_EVENTS = {
    "capability_sheet_opened",
    "capability_launched",
    "capability_guide_viewed",  # Task 53 (manual page) reuses this path.
}


class ClientMetricIn(BaseModel):
    name: str = Field(..., min_length=1, max_length=64)
    props: dict | None = None


@router.post("/event")
async def record_metric(
    payload: ClientMetricIn, ctx: WebUserCtx = Depends(verify_supabase_jwt)
):
    """Record one allowlisted client UI metric into analytics_events."""
    if payload.name not in _ALLOWED_EVENTS:
        raise HTTPException(status_code=422, detail="Unknown metric")
    emit_metric_now(payload.name, user_id=ctx.user_id, payload=payload.props or {})
    return {"ok": True}
