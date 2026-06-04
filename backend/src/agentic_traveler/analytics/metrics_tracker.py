"""
In-memory metrics buffer with periodic Supabase flush.

Buffers lightweight counters (interactions, new users, active users,
token usage per model/agent) in memory and writes a single roll-up
row to the ``analytics_weekly`` table once per week (Sunday closing).
Also supports on-demand flush — both async (default) and synchronous
(for shutdown).

Supabase layout (``analytics_weekly`` table):
    week_ending        : DATE  (PK)
    total_interactions : INT
    new_users          : INT
    agent_calls        : JSONB  — {agent: count}
    token_usage        : JSONB  — {model: {input: int, output: int}}
    promo_redeemed     : JSONB  — {code: count}
    grounding_calls    : INT
    flushed_at         : TIMESTAMPTZ
"""

import atexit
import logging
import os
import sys
import threading
from datetime import date, datetime, timedelta, timezone
from typing import Any, Dict

logger = logging.getLogger(__name__)

# ── configuration ──────────────────────────────────────────────────────────

# How often to auto-flush (seconds). Default: hourly (3600 s).
FLUSH_INTERVAL = int(os.getenv("METRICS_FLUSH_INTERVAL", "3600"))

# Minimum events before a flush is worthwhile
MIN_EVENTS_TO_FLUSH = 1

# Maximum events to buffer before auto-flushing regardless of interval
FLUSH_THRESHOLD = int(os.getenv("METRICS_FLUSH_THRESHOLD", "100"))

# ── in-memory counters ─────────────────────────────────────────────────────

_lock = threading.RLock()

_total_interactions: int = 0
_new_users: int = 0
_agent_calls: Dict[str, int] = {}
_token_usage: Dict[str, Dict[str, int]] = {}  # model → {input, output}
_event_count: int = 0
_promo_redeemed: Dict[str, int] = {}  # promo code → times redeemed
_grounding_calls: int = 0  # sub-agent calls that triggered Google Search


def _reset_locked() -> None:
    """Reset all in-memory counters. For testing use only."""
    global _total_interactions, _new_users, _event_count, _grounding_calls
    with _lock:
        _total_interactions = 0
        _new_users = 0
        _agent_calls.clear()
        _token_usage.clear()
        _promo_redeemed.clear()
        _grounding_calls = 0
        _event_count = 0


# ── public recording API ──────────────────────────────────────────────────


def record_interaction(*, user_id: str, is_new_user: bool = False) -> None:
    """Record a single user interaction (called per webhook request)."""
    global _total_interactions, _new_users, _event_count

    with _lock:
        _total_interactions += 1
        if is_new_user:
            _new_users += 1
        _event_count += 1
        if _event_count >= FLUSH_THRESHOLD:
            _flush_locked()


def record_token_usage(
    *,
    agent_name: str,
    model_name: str,
    input_tokens: int,
    output_tokens: int,
    total_cost_credits: int = 0,
) -> None:
    """Record token usage from an LLM call (called by usage_tracker)."""
    global _event_count

    with _lock:
        _agent_calls[agent_name] = _agent_calls.get(agent_name, 0) + 1

        safe_model = model_name.replace(".", "_").replace("/", "_")
        if safe_model not in _token_usage:
            _token_usage[safe_model] = {"input": 0, "output": 0, "call_count": 0, "total_cost_credits": 0}
        _token_usage[safe_model]["input"] += input_tokens
        _token_usage[safe_model]["output"] += output_tokens
        _token_usage[safe_model]["call_count"] += 1
        _token_usage[safe_model]["total_cost_credits"] += total_cost_credits
        _event_count += 1
        if _event_count >= FLUSH_THRESHOLD:
            _flush_locked()


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


def _get_week_key(reference_date: datetime | date | None = None) -> str:
    """Return the ISO date string for the coming Sunday (week-ending key)."""
    if reference_date is None:
        reference_date = datetime.now(timezone.utc)

    if isinstance(reference_date, date) and not isinstance(reference_date, datetime):
        reference_date = datetime.combine(reference_date, datetime.min.time(), tzinfo=timezone.utc)
    elif reference_date.tzinfo is None:
        reference_date = reference_date.replace(tzinfo=timezone.utc)

    days_until_sunday = (6 - reference_date.weekday()) % 7
    sunday = reference_date + timedelta(days=days_until_sunday)
    return sunday.strftime("%Y-%m-%d")


def _week_ending_key() -> str:
    """Wrapper for backward compatibility or internal use."""
    return _get_week_key()


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
            "agent_calls": dict(_agent_calls),
            "token_usage": {k: dict(v) for k, v in _token_usage.items()},
            "promo_redeemed": dict(_promo_redeemed),
            "grounding_calls": _grounding_calls,
            "event_count": _event_count,
        }

        _total_interactions = 0
        _new_users = 0
        _agent_calls.clear()
        _token_usage.clear()
        _promo_redeemed.clear()
        _grounding_calls = 0
        _event_count = 0

    return snapshot


def _write_to_supabase(snapshot: Dict[str, Any]) -> None:
    """Merge a snapshot into the weekly analytics row via Supabase upsert."""
    from agentic_traveler.tools.db_client import get_db

    try:
        doc_key = _week_ending_key()

        # Fetch existing row so we can merge counts (no atomic increment in REST API)
        resp = (
            get_db()
            .table("analytics_weekly")
            .select("*")
            .eq("week_ending", doc_key)
            .maybe_single()
            .execute()
        )
        
        # Handle cases where execute() might return None due to network/init issues
        if resp is None:
            logger.error("Supabase execute() returned None for analytics fetch. defaulting to empty record.")
            existing = {}
        else:
            existing = resp.data or {}

        # Merge numeric fields
        merged: Dict[str, Any] = {
            "week_ending": doc_key,
            "total_interactions": existing.get("total_interactions", 0)
                                  + snapshot["total_interactions"],
            "new_users": existing.get("new_users", 0) + snapshot["new_users"],
            "grounding_calls": existing.get("grounding_calls", 0)
                               + snapshot["grounding_calls"],
            "flushed_at": datetime.now(timezone.utc).isoformat(),
        }



        # Merge agent_calls (JSONB dict of counts)
        merged_agent_calls = dict(existing.get("agent_calls") or {})
        for agent, count in snapshot["agent_calls"].items():
            merged_agent_calls[agent] = merged_agent_calls.get(agent, 0) + count
        merged["agent_calls"] = merged_agent_calls

        # Merge token_usage
        merged_token_usage = dict(existing.get("token_usage") or {})
        for model, tokens in snapshot["token_usage"].items():
            existing_model = merged_token_usage.get(model, {"input": 0, "output": 0, "call_count": 0, "total_cost_credits": 0})
            merged_token_usage[model] = {
                "input": existing_model.get("input", 0) + tokens["input"],
                "output": existing_model.get("output", 0) + tokens["output"],
                "call_count": existing_model.get("call_count", 0) + tokens.get("call_count", 0),
                "total_cost_credits": existing_model.get("total_cost_credits", 0) + tokens.get("total_cost_credits", 0),
            }
        merged["token_usage"] = merged_token_usage

        # Sum total weekly cost from all models
        total_cost_credits = sum(
            model_data.get("total_cost_credits", 0)
            for model_data in merged_token_usage.values()
        )
        merged["total_cost_credits"] = total_cost_credits

        # Merge promo_redeemed
        merged_promos = dict(existing.get("promo_redeemed") or {})
        for code, count in snapshot["promo_redeemed"].items():
            merged_promos[code] = merged_promos.get(code, 0) + count
        merged["promo_redeemed"] = merged_promos

        get_db().table("analytics_weekly").upsert(merged).execute()

        logger.info(
            "📊 Metrics flushed → analytics_weekly/%s (%d events)",
            doc_key,
            snapshot["event_count"],
        )
    except Exception:
        logger.exception("Failed to flush metrics to Supabase.")


def _flush_locked(sync: bool = False) -> None:
    """Internal flush: snapshot then write (sync or async)."""
    snapshot = _take_snapshot()
    if snapshot is None:
        return

    if sync:
        logger.info("Performing synchronous metrics flush...")
        _write_to_supabase(snapshot)
    else:
        t = threading.Thread(
            target=_write_to_supabase, args=(snapshot,), daemon=True
        )
        t.start()


def flush(sync: bool = False) -> None:
    """Public API — flush buffered metrics to Supabase.

    Args:
        sync: If True the Supabase write happens in the calling thread
              (blocking).  Use this during SIGTERM / atexit shutdown so
              the write completes before the process exits.
    """
    _flush_locked(sync=sync)


# ── auto-flush on exit ────────────────────────────────────────────────────

# Avoid registering atexit handler under pytest to prevent bad file descriptor logging errors
if "pytest" not in sys.modules and "PYTEST_CURRENT_TEST" not in os.environ:
    atexit.register(flush, sync=True)
