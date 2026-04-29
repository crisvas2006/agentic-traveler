"""
Token usage logging and per-user Firestore accumulation.

Two responsibilities:
1. **Structured logging** — emit a JSON-style log line per LLM call
   (picked up by Cloud Logging for free on Cloud Run).
2. **Firestore accumulation** — increment per-model token totals on the
   user document so we can query per-user cost at any time.

Firestore layout (under each user doc):
    usage/
        <model_name>/
            total_input_tokens: int
            total_output_tokens: int
            call_count: int
            grounded_prompt_count: int   # how many calls triggered grounding
"""

import logging
from typing import Any, Dict

from google.cloud.firestore_v1 import transforms

from agentic_traveler import credit_manager as _credit_manager

logger = logging.getLogger(__name__)


def log_and_accumulate(
    *,
    agent_name: str,
    model_name: str,
    user_id: str,
    response: Any,
    latency_ms: float,
    user_doc_ref: Any = None,
) -> Dict[str, Any]:
    """
    Log token usage and accumulate totals in Firestore.

    Args:
        agent_name: Which agent made the call (e.g. "orchestrator").
        model_name: Model used (e.g. "gemini-2.5-flash").
        user_id: Firestore user document ID.
        response: The GenAI response object (has .usage_metadata).
        latency_ms: How long the call took in milliseconds.
        user_doc_ref: Firestore DocumentReference (optional).

    Returns:
        Dict with input_tokens, output_tokens, total_tokens, model_name,
        grounding_used (bool), grounding_cost_credits (int).
    """
    input_tokens = 0
    output_tokens = 0

    usage = getattr(response, "usage_metadata", None)
    if usage:
        input_tokens = getattr(usage, "prompt_token_count", 0) or 0
        output_tokens = getattr(usage, "candidates_token_count", 0) or 0

    total_tokens = input_tokens + output_tokens

    # Detect grounding: check if any candidate has non-empty grounding_metadata
    grounding_used = _detect_grounding(response)
    grounding_cost_credits = (
        _credit_manager.calculate_grounding_cost(1) if grounding_used else 0
    )

    # Structured log line (Cloud Logging picks this up automatically)
    logger.info(
        "📊 LLM usage | agent=%s model=%s user=%s "
        "input_tokens=%d output_tokens=%d total_tokens=%d "
        "latency_ms=%.0f grounding_used=%s",
        agent_name, model_name, user_id,
        input_tokens, output_tokens, total_tokens, latency_ms, grounding_used,
    )

    # Accumulate in Firestore (uses atomic increment)
    if user_doc_ref and total_tokens > 0:
        _accumulate_firestore(
            user_doc_ref, model_name, input_tokens, output_tokens, grounding_used
        )

    # Roll up into global weekly metrics buffer (fire-and-forget, no I/O here)
    if total_tokens > 0:
        try:
            from agentic_traveler import metrics_tracker
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
            from agentic_traveler import metrics_tracker
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
            # grounding_metadata is populated when search was actually used
            chunks = getattr(meta, "grounding_chunks", None)
            if chunks:
                return True
    except Exception:
        pass
    return False


def _accumulate_firestore(
    user_doc_ref: Any,
    model_name: str,
    input_tokens: int,
    output_tokens: int,
    grounding_used: bool = False,
) -> None:
    """Atomically increment per-model token counters on the user doc."""
    # Sanitize model name for use as Firestore field path
    # (dots in model names would be interpreted as nested paths)
    safe_model = model_name.replace(".", "_").replace("/", "_")
    prefix = f"usage.{safe_model}"

    update: Dict[str, Any] = {
        f"{prefix}.total_input_tokens": transforms.Increment(input_tokens),
        f"{prefix}.total_output_tokens": transforms.Increment(output_tokens),
        f"{prefix}.call_count": transforms.Increment(1),
    }
    if grounding_used:
        update[f"{prefix}.grounded_prompt_count"] = transforms.Increment(1)

    try:
        user_doc_ref.update(update)
    except Exception:
        logger.exception("Failed to accumulate usage for model %s.", model_name)

