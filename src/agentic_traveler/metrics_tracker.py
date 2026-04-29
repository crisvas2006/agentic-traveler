"""
In-memory metrics buffer with periodic Firestore flush.

Buffers lightweight counters (interactions, new users, active users,
token usage per model/agent) in memory and writes a single roll-up
document to Firestore once per week (Sunday closing).  Also supports
on-demand flush — both async (default) and synchronous (for shutdown).

Firestore layout:
    analytics/<week_ending_YYYY-MM-DD>/
        total_interactions: int
        new_users: int
        active_users: [str]         # deduplicated user IDs
        agent_calls: {agent: count}
        token_usage: {model: {input: int, output: int}}
        flushed_at: timestamp
"""

import atexit
import logging
import os
import threading
from datetime import datetime, timedelta, timezone
from typing import Any, Dict

logger = logging.getLogger(__name__)

# ── configuration ──────────────────────────────────────────────────────────

# How often to auto-flush (seconds). Default: hourly (3600 s).
FLUSH_INTERVAL = int(os.getenv("METRICS_FLUSH_INTERVAL", "3600"))

# Minimum events before a flush is worthwhile
MIN_EVENTS_TO_FLUSH = 1

# ── in-memory counters ─────────────────────────────────────────────────────

_lock = threading.Lock()

_total_interactions: int = 0
_new_users: int = 0
_active_users: set[str] = set()
_agent_calls: Dict[str, int] = {}
_token_usage: Dict[str, Dict[str, int]] = {}  # model → {input, output}
_event_count: int = 0
_promo_redeemed: Dict[str, int] = {}  # promo code → times redeemed
_grounding_calls: int = 0  # sub-agent calls that triggered Google Search


# ── public recording API ──────────────────────────────────────────────────


def record_interaction(*, user_id: str, is_new_user: bool = False) -> None:
    """Record a single user interaction (called per webhook request)."""
    global _total_interactions, _new_users, _event_count

    with _lock:
        _total_interactions += 1
        _active_users.add(user_id)
        if is_new_user:
            _new_users += 1
        _event_count += 1


def record_token_usage(
    *,
    agent_name: str,
    model_name: str,
    input_tokens: int,
    output_tokens: int,
) -> None:
    """Record token usage from an LLM call (called by usage_tracker)."""
    global _event_count

    with _lock:
        # Agent call counter
        _agent_calls[agent_name] = _agent_calls.get(agent_name, 0) + 1

        # Per-model token accumulator
        safe_model = model_name.replace(".", "_").replace("/", "_")
        if safe_model not in _token_usage:
            _token_usage[safe_model] = {"input": 0, "output": 0}
        _token_usage[safe_model]["input"] += input_tokens
        _token_usage[safe_model]["output"] += output_tokens
        _event_count += 1


def record_promo_redeemed(code: str) -> None:
    """Record a successful promo code redemption (called by credit_manager)."""
    with _lock:
        normalized = code.strip().upper()
        _promo_redeemed[normalized] = _promo_redeemed.get(normalized, 0) + 1


def record_grounding_used() -> None:
    """Record that Google Search grounding fired for a sub-agent call."""
    global _grounding_calls
    with _lock:
        _grounding_calls += 1


# ── flush logic ───────────────────────────────────────────────────────────


def _week_ending_key() -> str:
    """Return the ISO date string for the coming Sunday (week-ending key)."""
    now = datetime.now(timezone.utc)
    days_until_sunday = (6 - now.weekday()) % 7 or 7
    sunday = now + timedelta(days=days_until_sunday)
    return sunday.strftime("%Y-%m-%d")


def _take_snapshot() -> Dict[str, Any] | None:
    """Atomically snapshot and reset all in-memory counters.

    Returns None if there is nothing to flush.
    """
    global _total_interactions, _new_users, _event_count, _grounding_calls

    with _lock:
        if _event_count < MIN_EVENTS_TO_FLUSH:
            return None

        snapshot = {
            "total_interactions": _total_interactions,
            "new_users": _new_users,
            "active_users": list(_active_users),
            "agent_calls": dict(_agent_calls),
            "token_usage": {k: dict(v) for k, v in _token_usage.items()},
            "promo_redeemed": dict(_promo_redeemed),
            "grounding_calls": _grounding_calls,
            "event_count": _event_count,
        }

        # Reset
        _total_interactions = 0
        _new_users = 0
        _active_users.clear()
        _agent_calls.clear()
        _token_usage.clear()
        _promo_redeemed.clear()
        _grounding_calls = 0
        _event_count = 0

    return snapshot


def _write_to_firestore(snapshot: Dict[str, Any]) -> None:
    """Merge a snapshot into the weekly analytics document."""
    try:
        from google.cloud import firestore as fs
        from google.cloud.firestore_v1 import transforms

        project = os.getenv("GOOGLE_PROJECT_ID")
        db = fs.Client(project=project, database="agentic-traveler-db")

        doc_key = _week_ending_key()
        doc_ref = db.collection("analytics").document(doc_key)

        # Use atomic increments for numeric fields; array-union for users
        update: Dict[str, Any] = {
            "total_interactions": transforms.Increment(
                snapshot["total_interactions"]
            ),
            "new_users": transforms.Increment(snapshot["new_users"]),
            "active_users": transforms.ArrayUnion(snapshot["active_users"]),
            "flushed_at": fs.SERVER_TIMESTAMP,
        }

        # Merge agent call counts
        for agent, count in snapshot["agent_calls"].items():
            update[f"agent_calls.{agent}"] = transforms.Increment(count)

        # Merge token usage
        for model, tokens in snapshot["token_usage"].items():
            update[f"token_usage.{model}.input"] = transforms.Increment(
                tokens["input"]
            )
            update[f"token_usage.{model}.output"] = transforms.Increment(
                tokens["output"]
            )

        # Merge promo redemption counts
        for code, count in snapshot["promo_redeemed"].items():
            update[f"promo_redeemed.{code}"] = transforms.Increment(count)

        # Merge grounding call count
        if snapshot["grounding_calls"] > 0:
            update["grounding_calls"] = transforms.Increment(snapshot["grounding_calls"])

        doc_ref.set(update, merge=True)

        logger.info(
            "📊 Metrics flushed → analytics/%s (%d events)",
            doc_key,
            snapshot["event_count"],
        )
    except Exception:
        logger.exception("Failed to flush metrics to Firestore.")


def _flush_locked(sync: bool = False) -> None:
    """Internal flush: snapshot then write (sync or async)."""
    snapshot = _take_snapshot()
    if snapshot is None:
        return

    if sync:
        logger.info("Performing synchronous metrics flush...")
        _write_to_firestore(snapshot)
    else:
        t = threading.Thread(
            target=_write_to_firestore, args=(snapshot,), daemon=True
        )
        t.start()


def flush(sync: bool = False) -> None:
    """Public API — flush buffered metrics to Firestore.

    Args:
        sync: If True the Firestore write happens in the calling thread
              (blocking).  Use this during SIGTERM / atexit shutdown so
              the write completes before the process exits.
    """
    _flush_locked(sync=sync)


# ── auto-flush on exit ────────────────────────────────────────────────────

atexit.register(flush, sync=True)
