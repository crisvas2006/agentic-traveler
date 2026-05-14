"""
Token usage logging and per-user Supabase accumulation.

Two responsibilities:
1. **Structured logging** — emit a JSON-style log line per LLM call
   (picked up by Cloud Logging for free on Cloud Run).
2. **Supabase accumulation** — upsert per-model token totals into the
   ``usage_tracking`` table so we can query per-user cost at any time.

Supabase layout (``usage_tracking`` table):
    user_id               : UUID
    model_name            : TEXT
    total_input_tokens    : BIGINT
    total_output_tokens   : BIGINT
    call_count            : INT
    grounded_prompt_count : INT
"""

import logging
from typing import Any, Dict

from agentic_traveler.economy import credit_manager as _credit_manager

logger = logging.getLogger(__name__)


def log_and_accumulate(
    *,
    agent_name: str,
    model_name: str,
    user_id: str,
    response: Any,
    latency_ms: float,
    user_doc_ref: Any = None,  # kept for backward compatibility, unused
) -> Dict[str, Any]:
    """
    Log token usage and accumulate totals in Supabase.

    Args:
        agent_name:  Which agent made the call (e.g. "orchestrator").
        model_name:  Model used (e.g. "gemini-2.5-flash").
        user_id:     Telegram user ID (used for logging) or UUID.
        response:    The GenAI response object (has .usage_metadata).
        latency_ms:  How long the call took in milliseconds.
        user_doc_ref: Ignored — kept to avoid breaking call sites.

    Returns:
        Dict with input_tokens, output_tokens, total_tokens, model_name,
        grounding_used (bool), grounding_cost_credits (int).
    """
    input_tokens = 0
    output_tokens = 0

    usage = getattr(response, "usage_metadata", None)
    if usage:
        input_tokens = int(getattr(usage, "prompt_token_count", 0) or 0)
        output_tokens = int(getattr(usage, "candidates_token_count", 0) or 0)

    total_tokens = input_tokens + output_tokens

    grounding_used = _detect_grounding(response)
    grounding_cost_credits = (
        _credit_manager.calculate_grounding_cost(1) if grounding_used else 0
    )

    logger.info(
        "📊 LLM usage | agent=%s model=%s user=%s "
        "input_tokens=%d output_tokens=%d total_tokens=%d "
        "latency_ms=%.0f grounding_used=%s",
        agent_name, model_name, user_id,
        input_tokens, output_tokens, total_tokens, latency_ms, grounding_used,
    )

    # Accumulate in Supabase (the user_id here is the telegram_id string;
    # accumulation is best-effort and non-blocking via the metrics buffer)
    if total_tokens > 0:
        try:
            from agentic_traveler.analytics import metrics_tracker
            metrics_tracker.record_token_usage(
                agent_name=agent_name,
                model_name=model_name,
                input_tokens=input_tokens,
                output_tokens=output_tokens,
            )
        except Exception:
            logger.exception("Failed to record token usage in metrics_tracker.")

    if grounding_used:
        try:
            from agentic_traveler.analytics import metrics_tracker
            metrics_tracker.record_grounding_used()
        except Exception:
            logger.exception("Failed to record grounding metric.")

    return {
        "input_tokens": input_tokens,
        "output_tokens": output_tokens,
        "total_tokens": total_tokens,
        "model_name": model_name,
        "grounding_used": grounding_used,
        "grounding_cost_credits": grounding_cost_credits,
    }


def _detect_grounding(response: Any) -> bool:
    """Return True if the response contains non-empty grounding metadata."""
    try:
        candidates = getattr(response, "candidates", None) or []
        for candidate in candidates:
            meta = getattr(candidate, "grounding_metadata", None)
            if meta is None:
                continue
            chunks = getattr(meta, "grounding_chunks", None)
            if chunks:
                return True
    except Exception:
        pass
    return False
