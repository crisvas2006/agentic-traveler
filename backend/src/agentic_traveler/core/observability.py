"""LangSmith bootstrap, privacy-preserving identifier hashing, kill switch.

This module is the SINGLE place where we touch LangSmith APIs other than the
`@traceable` decorator imported from `langsmith` directly. Keeps the import
surface tiny and the kill switch local.
"""

from __future__ import annotations

import hashlib
import hmac
import logging
import os
from typing import Any, Callable, TypeVar

logger = logging.getLogger(__name__)

_TRACING_ENABLED = os.getenv("LANGSMITH_TRACING", "false").lower() == "true"
_HASH_KEY = os.getenv("LANGSMITH_HASH_KEY", "")
_warned_no_hash_key = False


def is_tracing_enabled() -> bool:
    return _TRACING_ENABLED


def hash_user_id(user_id: str | None) -> str:
    """
    HMAC-SHA256 of the internal users.id UUID under LANGSMITH_HASH_KEY.
    Reversible only by us (server-side secret). Safe to send to LangSmith.
    """
    if not user_id:
        return "anonymous"
    if not _HASH_KEY:
        # One-time WARN; subsequent calls silent (rate-limit via module flag).
        global _warned_no_hash_key
        if not _warned_no_hash_key:
            logger.warning(
                "LANGSMITH_HASH_KEY not set — user correlation in LangSmith "
                "degraded to 'unknown'. Tracing still active."
            )
            _warned_no_hash_key = True
        return "unknown"
    return hmac.new(
        _HASH_KEY.encode("utf-8"),
        user_id.encode("utf-8"),
        hashlib.sha256,
    ).hexdigest()


F = TypeVar("F", bound=Callable[..., Any])

# Re-export `@traceable` from langsmith so callers import from observability,
# not langsmith directly. This keeps `langsmith` swappable/removable in one
# place. When LANGSMITH_TRACING is false the decorator is a no-op pass-through.
if _TRACING_ENABLED:
    try:
        from langsmith import traceable as _traceable  # type: ignore[import-not-found]

        traceable = _traceable
        logger.info("LangSmith tracing enabled.")
    except Exception:
        logger.warning("langsmith import failed; tracing disabled.", exc_info=True)

        def traceable(*dargs, **dkwargs):  # type: ignore[no-redef]
            def _decorator(fn: F) -> F:
                return fn
            return _decorator
else:
    def traceable(*dargs, **dkwargs):  # type: ignore[no-redef]
        def _decorator(fn: F) -> F:
            return fn
        return _decorator


def attach_run_metadata(**kw: Any) -> None:
    """
    Attach NON-PII metadata to the current run, if tracing is on.
    Safe to call when tracing is off (no-op).
    """
    if not _TRACING_ENABLED:
        return
    try:
        from langsmith.run_helpers import get_current_run_tree  # type: ignore[import-not-found]
        rt = get_current_run_tree()
        if rt is not None:
            rt.metadata.update(kw)
    except Exception:
        pass  # never let observability errors break the request


def record_run_error(message: str) -> None:
    """
    Flag the current run as errored in LangSmith without raising.

    The orchestrator catches agent failures and returns a graceful fallback to
    the user, so nothing propagates as an exception — which means LangSmith
    would otherwise record the trace as successful. Setting the run tree's
    ``error`` field surfaces the failure (red run) so it's queryable. Best-effort
    and a no-op when tracing is off.
    """
    if not _TRACING_ENABLED:
        return
    try:
        from langsmith.run_helpers import get_current_run_tree  # type: ignore[import-not-found]
        rt = get_current_run_tree()
        if rt is not None:
            rt.error = message
            rt.metadata.update({"agent_failed": True})
    except Exception:
        pass  # never let observability errors break the request
