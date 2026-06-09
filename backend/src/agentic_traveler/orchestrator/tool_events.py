"""Tool-status plumbing (Task 37).

The heavy agents call tools (``check_weather``, ``search_web``) via Gemini
automatic function calling, so the orchestrator can't see the tool boundary
directly. Instead we stash the current turn's ``EventEmitter`` in a contextvar
right before the model call; the tool functions read it and emit a
``status`` event the moment the SDK invokes them ("Checking the weather…").

A contextvar (not a module global) is used so concurrent turns — each running
in its own thread / asyncio context (Cloud Run concurrency ≥100) — never see
each other's emitter.
"""

from __future__ import annotations

import contextvars
import logging
from typing import Any, Optional

from agentic_traveler.orchestrator.event_text_registry import text_for

logger = logging.getLogger(__name__)

_current_emitter: contextvars.ContextVar[Optional[Any]] = contextvars.ContextVar(
    "current_emitter", default=None
)


def set_current_emitter(events: Optional[Any]) -> Any:
    """Bind the active EventEmitter for the current context. Returns a token to
    pass back to ``reset_current_emitter`` in a finally block."""
    return _current_emitter.set(events)


def reset_current_emitter(token: Any) -> None:
    try:
        _current_emitter.reset(token)
    except (ValueError, LookupError):
        # Token from a different context (defensive) — ignore.
        pass


def emit_tool_status(tool_name: str) -> None:
    """Emit a ``status`` event for a tool invocation, if an emitter is bound and
    the tool maps to a user-visible string. No-op otherwise — safe to call from
    any tool unconditionally."""
    events = _current_emitter.get()
    if events is None:
        return
    text = text_for("tool", tool_name)
    if not text:
        return
    try:
        events.emit("status", {"phase": "tool", "tool": tool_name, "text": text})
    except Exception:
        logger.debug("emit_tool_status failed for %s", tool_name, exc_info=True)
