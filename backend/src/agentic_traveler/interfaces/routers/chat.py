"""
Web chat router.

Endpoints (all require a valid Supabase JWT):
    POST /chat/send       — send a message, get the agent reply.
    GET  /chat/messages   — cursor-paginated history (newest-first).
    GET  /chat/search     — full-text search across the user's thread.
"""

import asyncio
import json
import logging
import time
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from fastapi.responses import StreamingResponse

from agentic_traveler.core.sanitize import sanitize_user_input
from agentic_traveler.interfaces.dependencies import WebUserCtx, verify_supabase_jwt
from agentic_traveler.interfaces.schemas import (
    ChatHistoryResponse,
    ChatMessageOut,
    ChatSearchResponse,
    ChatSendRequest,
    ChatSendResponse,
)
from agentic_traveler.orchestrator.sagas.planning import ui_block_from_wire
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


# ── SSE streaming helpers (Task 37) ────────────────────────────────────────

def _sse(event: str, data: dict) -> str:
    """Format one Server-Sent Event frame."""
    return f"event: {event}\ndata: {json.dumps(data, ensure_ascii=False)}\n\n"


def _reply_metadata(action, latency_ms: int, slot_request) -> dict:
    """Build the agent message's ``metadata``: always the action + latency, plus
    a ``ui`` block (multiple-choice / quick-reply chips, Task 43) when the reply
    carries tappable choices. Replies without choices leave ``ui`` unset."""
    metadata: dict = {"action": action, "latency_ms": latency_ms}
    ui = ui_block_from_wire(slot_request)
    if ui:
        metadata["ui"] = ui
    return metadata


@router.post("/send", response_model=ChatSendResponse)
async def chat_send(payload: ChatSendRequest, ctx: WebUserCtx = Depends(verify_supabase_jwt)):
    """Persist the user message, run the orchestrator, persist the reply.

    When ``payload.selection`` is present the message is a tapped chip: ``body``
    is the chosen label (shown in the bubble) and the structured selection is
    applied deterministically (no slot_extractor LLM call — Task 43)."""
    body = sanitize_user_input(payload.body)
    if not body:
        raise HTTPException(status_code=400, detail="Empty message")
    selection = payload.selection.model_dump() if payload.selection else None

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
            selection=selection,
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

    # 3. Persist the agent reply (with a ui block when it carries choices).
    try:
        agent_row = repo.append_agent_message(
            ctx.user_id,
            reply_text,
            source="web",
            thread_id=user_row["thread_id"],
            metadata=_reply_metadata(
                agent_result.get("action"), latency_ms,
                agent_result.get("slot_request"),
            ),
        )
    except Exception:
        logger.exception("Failed to persist agent reply for user %s", ctx.user_id)
        raise HTTPException(status_code=500, detail="Failed to save reply")

    return ChatSendResponse(
        user_message=ChatMessageOut(**user_row),
        reply=ChatMessageOut(**agent_row),
    )


@router.post("/stream")
async def chat_stream(payload: ChatSendRequest, ctx: WebUserCtx = Depends(verify_supabase_jwt)):
    """Streaming variant of /send (Task 37).

    Emits Server-Sent Events: `status` (intermediate progress), `delta` (the
    reply, chunked), and a final `done` carrying the persisted `message_id`.
    The agent reply is persisted to `messages` BEFORE the deltas stream, so a
    dropped SSE connection still leaves the reply recoverable via Realtime
    (AC-6). The non-streaming /send endpoint is unchanged.
    """
    body = sanitize_user_input(payload.body)
    if not body:
        raise HTTPException(status_code=400, detail="Empty message")

    repo = _get_chat_repo()
    try:
        user_row = repo.append_user_message(ctx.user_id, body, source="web")
    except Exception:
        logger.exception("Failed to persist user message for user %s", ctx.user_id)
        raise HTTPException(status_code=500, detail="Failed to save message")
    thread_id = user_row["thread_id"]

    loop = asyncio.get_running_loop()
    queue: asyncio.Queue = asyncio.Queue()

    def push(ev_type: str, data: dict) -> None:
        # Called from the worker thread → marshal back onto the event loop.
        loop.call_soon_threadsafe(queue.put_nowait, (ev_type, data))

    async def driver() -> None:
        t = time.time()
        action = None
        slot_request = None
        try:
            result = await asyncio.to_thread(
                _get_orchestrator().process_request_for_user,
                ctx.user_id,
                body,
                lambda p: push("status", p),   # status_callback → SSE `status` events
                lambda p: push("delta", p),    # delta_callback → real token `delta` events
            )
            text = result.get("text") or (
                "I had trouble coming up with a response just now. Please try again."
            )
            action = result.get("action")
            slot_request = result.get("slot_request")
        except Exception:
            logger.exception("Streaming orchestrator failed for user %s", ctx.user_id)
            push("status", {"phase": "error", "text": "Something glitched. Please try again."})
            text = "Sorry, I hit an error processing your message. Please try again."
            action = "ERROR"

        latency_ms = int((time.time() - t) * 1000)
        ui = ui_block_from_wire(slot_request)
        message_id = None
        try:
            agent_row = repo.append_agent_message(
                ctx.user_id, text, source="web", thread_id=thread_id,
                metadata=_reply_metadata(action, latency_ms, slot_request),
            )
            message_id = agent_row["id"]
        except Exception:
            logger.exception("Failed to persist streamed reply for user %s", ctx.user_id)

        # `text` is included on `done` as a fallback: not every turn streams
        # deltas (slot questions, off-topic redirects, and the error path return
        # text directly without an agent call), and the client also uses it to
        # reconcile against the streamed deltas. `ui` carries any tappable choice
        # block (Task 43) so the client renders chips on the just-streamed reply
        # without waiting for a Realtime round-trip. `user_message_id` +
        # `thread_id` let the client finalize its optimistic user bubble and
        # de-duplicate the Realtime echo of both rows against the SSE stream.
        push("done", {
            "message_id": message_id,
            "user_message_id": user_row["id"],
            "thread_id": thread_id,
            "latency_ms": latency_ms,
            "text": text,
            "ui": ui,
        })

    driver_task = asyncio.create_task(driver())

    async def gen():
        try:
            while True:
                ev_type, data = await queue.get()
                yield _sse(ev_type, data)
                if ev_type == "done":
                    break
        finally:
            # Client disconnected or stream finished — never leave the worker dangling.
            if not driver_task.done():
                driver_task.cancel()

    return StreamingResponse(
        gen(),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
    )


@router.get("/messages", response_model=ChatHistoryResponse)
async def chat_messages(
    before: Optional[int] = Query(default=None, description="Return messages with id < before"),
    after: Optional[int] = Query(default=None, description="Return messages with id > after"),
    around: Optional[int] = Query(default=None, description="Return messages around id"),
    limit: int = Query(default=50, ge=1, le=100),
    ctx: WebUserCtx = Depends(verify_supabase_jwt),
):
    """Cursor-paginated history. Returns rows in id DESC order (newest first)."""
    repo = _get_chat_repo()
    
    if around is not None:
        half_limit = limit // 2
        # before_id is exclusive, so around + 1 includes `around` if it exists.
        older = repo.list_messages(ctx.user_id, before_id=around + 1, limit=half_limit + 1)
        # newer asks for strictly > around
        newer = repo.list_messages(ctx.user_id, after_id=around, limit=limit - len(older))
        rows = newer + older
        has_more = len(older) == half_limit + 1
        has_more_newer = len(newer) == limit - len(older)
    elif after is not None:
        rows = repo.list_messages(ctx.user_id, after_id=after, limit=limit)
        has_more = True
        has_more_newer = len(rows) == limit
    else:
        rows = repo.list_messages(ctx.user_id, before_id=before, limit=limit)
        has_more = len(rows) == limit
        has_more_newer = before is not None

    return ChatHistoryResponse(
        messages=[ChatMessageOut(**r) for r in rows],
        has_more=has_more,
        has_more_newer=has_more_newer,
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
