"""
Web chat router.

Endpoints (all require a valid Supabase JWT):
    POST /chat/send       — send a message, get the agent reply.
    GET  /chat/messages   — cursor-paginated history (newest-first).
    GET  /chat/search     — full-text search across the user's thread.
"""

import logging
import time
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query

from agentic_traveler.core.sanitize import sanitize_user_input
from agentic_traveler.interfaces.dependencies import WebUserCtx, verify_supabase_jwt
from agentic_traveler.interfaces.schemas import (
    ChatHistoryResponse,
    ChatMessageOut,
    ChatSearchResponse,
    ChatSendRequest,
    ChatSendResponse,
)
from agentic_traveler.tools.chat_repo import ChatRepository

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/chat", tags=["Chat"])

_chat_repo: ChatRepository | None = None
_orchestrator = None  # lazy import to avoid pulling the model client on cold start


def _get_chat_repo() -> ChatRepository:
    global _chat_repo
    if _chat_repo is None:
        _chat_repo = ChatRepository()
    return _chat_repo


def _get_orchestrator():
    """Reuse the same lazy-initialised orchestrator instance the Telegram router uses."""
    global _orchestrator
    if _orchestrator is None:
        # Reuse the Telegram router's lazily built instance so both channels
        # share AFC client state, conversation manager cache, etc.
        from agentic_traveler.interfaces.routers.telegram import get_orchestrator
        _orchestrator = get_orchestrator()
    return _orchestrator


@router.post("/send", response_model=ChatSendResponse)
async def chat_send(payload: ChatSendRequest, ctx: WebUserCtx = Depends(verify_supabase_jwt)):
    """Persist the user message, run the orchestrator, persist the reply."""
    body = sanitize_user_input(payload.body)
    if not body:
        raise HTTPException(status_code=400, detail="Empty message")

    repo = _get_chat_repo()

    # 1. Persist the user message first, so it survives an orchestrator crash.
    try:
        user_row = repo.append_user_message(ctx.user_id, body, source="web")
    except Exception:
        logger.exception("Failed to persist user message for user %s", ctx.user_id)
        raise HTTPException(status_code=500, detail="Failed to save message")

    # 2. Run the orchestrator (resolves user_doc internally, applies credit gate, etc.)
    t = time.time()
    try:
        agent_result = _get_orchestrator().process_request_for_user(
            user_id=ctx.user_id,
            message_text=body,
        )
    except Exception:
        logger.exception("Orchestrator failed for web user %s", ctx.user_id)
        # Still persist a failure reply so the conversation reflects what happened.
        agent_result = {
            "text": "Sorry, I hit an error processing your message. Please try again.",
            "action": "ERROR",
        }
    latency_ms = int((time.time() - t) * 1000)

    reply_text = agent_result.get("text", "")
    if not reply_text:
        reply_text = "I had trouble coming up with a response just now. Please try again."

    # 3. Persist the agent reply.
    try:
        agent_row = repo.append_agent_message(
            ctx.user_id,
            reply_text,
            source="web",
            thread_id=user_row["thread_id"],
            metadata={
                "action": agent_result.get("action"),
                "latency_ms": latency_ms,
            },
        )
    except Exception:
        logger.exception("Failed to persist agent reply for user %s", ctx.user_id)
        raise HTTPException(status_code=500, detail="Failed to save reply")

    return ChatSendResponse(
        user_message=ChatMessageOut(**user_row),
        reply=ChatMessageOut(**agent_row),
    )


@router.get("/messages", response_model=ChatHistoryResponse)
async def chat_messages(
    before: Optional[int] = Query(default=None, description="Return messages with id < before"),
    limit: int = Query(default=50, ge=1, le=100),
    ctx: WebUserCtx = Depends(verify_supabase_jwt),
):
    """Cursor-paginated history. Returns rows in id DESC order (newest first)."""
    rows = _get_chat_repo().list_messages(ctx.user_id, before_id=before, limit=limit)
    # `has_more` is true iff we returned a full page — caller paginates further.
    has_more = len(rows) == limit
    return ChatHistoryResponse(
        messages=[ChatMessageOut(**r) for r in rows],
        has_more=has_more,
    )


@router.get("/search", response_model=ChatSearchResponse)
async def chat_search(
    q: str = Query(..., min_length=1, max_length=200),
    limit: int = Query(default=25, ge=1, le=100),
    ctx: WebUserCtx = Depends(verify_supabase_jwt),
):
    """Full-text search inside the user's thread."""
    q = q.strip()
    if not q:
        raise HTTPException(status_code=400, detail="Empty query")
    rows = _get_chat_repo().search_messages(ctx.user_id, q, limit=limit)
    return ChatSearchResponse(results=[ChatMessageOut(**r) for r in rows])
