"""Profile router — Traveler-DNA writes (Task 54; extended by the DNA page, Task 57).

All endpoints require a valid Supabase JWT; the user id comes from the verified
token, never the request body. Profile chips POST here (rather than /chat/send) so a
tapped answer records silently without a chat bubble or trip resolution.
"""

import logging

from fastapi import APIRouter, Depends, HTTPException

from agentic_traveler.analytics.event_sink import emit_metric_now
from agentic_traveler.interfaces.dependencies import WebUserCtx, verify_supabase_jwt
from agentic_traveler.interfaces.schemas import ProfileAnswerIn, ProfileAnswerOut
from agentic_traveler.orchestrator.profile_questions import BY_ID
from agentic_traveler.orchestrator.profile_write import (
    apply_profile_patch,
    profile_selection_to_side_effect,
)

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/profile", tags=["Profile"])


@router.post("/answer", response_model=ProfileAnswerOut)
async def profile_answer(
    payload: ProfileAnswerIn, ctx: WebUserCtx = Depends(verify_supabase_jwt)
):
    """Apply a tapped Traveler-DNA answer (a profile chip). The question and the
    chosen value are re-validated against the bank server-side; an unknown question
    or an illegal option is rejected 422 with no write (Task 54 AC-4)."""
    se = profile_selection_to_side_effect(payload.qid, payload.values)
    if se is None:
        raise HTTPException(status_code=422, detail="Unknown question or illegal option")
    apply_profile_patch(ctx.user_id, se.payload)
    q = BY_ID.get(payload.qid)
    try:
        emit_metric_now(
            "profile_answer_written",
            user_id=ctx.user_id,
            payload={
                "id": payload.qid,
                "binding": q.binding if q else None,
                "source": "chat_tap",
                "method": "tap",
            },
        )
    except Exception:
        logger.exception("metric emit failed for profile_answer (user=%s)", ctx.user_id)
    return ProfileAnswerOut(qid=payload.qid, value=se.payload["value"])
