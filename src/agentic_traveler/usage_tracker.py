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
"""

import logging
from typing import Any, Dict

from google.cloud.firestore_v1 import transforms

logger = logging.getLogger(__name__)


def log_and_accumulate(
    *,
    agent_name: str,
    model_name: str,
    user_id: str,
    response: Any,
    latency_ms: float,
    user_doc_ref: Any = None,
) -> Dict[str, int]:
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
        Dict with input_tokens, output_tokens, total_tokens.
    """
    input_tokens = 0
    output_tokens = 0

    usage = getattr(response, "usage_metadata", None)
    if usage:
        input_tokens = getattr(usage, "prompt_token_count", 0) or 0
        output_tokens = getattr(usage, "candidates_token_count", 0) or 0

    total_tokens = input_tokens + output_tokens

    # Structured log line (Cloud Logging picks this up automatically)
    logger.info(
        "📊 LLM usage | agent=%s model=%s user=%s "
        "input_tokens=%d output_tokens=%d total_tokens=%d latency_ms=%.0f",
        agent_name, model_name, user_id,
        input_tokens, output_tokens, total_tokens, latency_ms,
    )

    # Accumulate in Firestore (uses atomic increment)
    if user_doc_ref and total_tokens > 0:
        _accumulate_firestore(user_doc_ref, model_name, input_tokens, output_tokens)

    return {
        "input_tokens": input_tokens,
        "output_tokens": output_tokens,
        "total_tokens": total_tokens,
    }


def _accumulate_firestore(
    user_doc_ref: Any,
    model_name: str,
    input_tokens: int,
    output_tokens: int,
) -> None:
    """Atomically increment per-model token counters on the user doc."""
    # Sanitize model name for use as Firestore field path
    # (dots in model names would be interpreted as nested paths)
    safe_model = model_name.replace(".", "_").replace("/", "_")
    prefix = f"usage.{safe_model}"

    try:
        user_doc_ref.update({
            f"{prefix}.total_input_tokens": transforms.Increment(input_tokens),
            f"{prefix}.total_output_tokens": transforms.Increment(output_tokens),
            f"{prefix}.call_count": transforms.Increment(1),
        })
    except Exception:
        logger.exception("Failed to accumulate usage for model %s.", model_name)
