"""
Per-user credit management.

Each user has a ``credits`` sub-document in Firestore::

    credits:
        balance: int           # current credit balance (≥ 0)
        initial_grant: int     # credits given at signup
        total_spent: int       # lifetime credits consumed
        used_promos: [str]     # promo codes already redeemed

1 credit = 1 eurocent.  New users receive DEFAULT_USER_CREDITS on signup.

Cost formula
------------
For every LLM call we know ``(model, input_tokens, output_tokens)``.

    raw_cost_usd = input_tokens / 1e6 * price_in + output_tokens / 1e6 * price_out
    raw_cost_eur = raw_cost_usd * USD_TO_EUR_RATE
    credits_used = max(1, ceil(raw_cost_eur * 100 * MARKUP_MULTIPLIER))

The markup covers infrastructure overhead and gives a safety
margin so the free-tier grant lasts a realistic number of interactions.
"""

import logging
import math
import os
import threading
from typing import Any, Dict, List, Optional, Tuple

from google.cloud.firestore_v1 import transforms  # type: ignore

from agentic_traveler.promo_codes import PROMO_CODES

logger = logging.getLogger(__name__)

# ── configuration ──────────────────────────────────────────────────────────

DEFAULT_USER_CREDITS = int(os.getenv("DEFAULT_USER_CREDITS", "500"))
USD_TO_EUR_RATE = float(os.getenv("USD_TO_EUR_RATE", "0.90"))
MARKUP_MULTIPLIER = 3
MARKUP_MULTIPLIER_GROUNDING = 2

# USD per 1 M tokens
MODEL_PRICING: Dict[str, Dict[str, float]] = {
    "gemini-2.5-flash":      {"input": 0.30, "output": 2.50},
    "gemini-2.5-flash-lite": {"input": 0.10, "output": 0.40},
    "gemini-3.0-flash":      {"input": 0.50, "output": 3.00},
}

# USD per grounded prompt (flat add-on charge, billed per sub-agent call that
# actually triggers a Google Search during generation)
GROUNDING_COST_PER_PROMPT_USD = 0.035  # $35 / 1,000 prompts

# Fallback if we encounter an unknown model
_DEFAULT_PRICING = {"input": 0.50, "output": 3.00}

# Static hardcoded message for zero-credit users (no LLM call needed)
CREDITS_EXHAUSTED_MSG = (
    "⚠️ You've used all your chat credits! You can still use the other features of the app.\n\n"
    "To keep chatting, you can:\n"
    "• Use a promo code: send /promo YOUR_CODE\n"
    "• Contact us for more credits\n\n"
    "Thanks for using Agentic Traveler! 🌍"
)


# ── public API ─────────────────────────────────────────────────────────────


def get_balance(user_doc: Dict[str, Any]) -> int:
    """Return the current credit balance from a user document dict."""
    return user_doc.get("credits", {}).get("balance", 0)


def has_credits(user_doc: Dict[str, Any]) -> bool:
    """Return True if the user has at least 1 credit remaining."""
    return get_balance(user_doc) >= 1


def initialize_credits(user_doc_ref: Any, amount: Optional[int] = None) -> None:
    """
    Set initial credit balance on a new user document.

    Args:
        user_doc_ref: Firestore DocumentReference.
        amount: Credits to grant (defaults to DEFAULT_USER_CREDITS).
    """
    grant = amount if amount is not None else DEFAULT_USER_CREDITS
    if user_doc_ref:
        user_doc_ref.set(
            {
                "credits": {
                    "balance": grant,
                    "initial_grant": grant,
                    "total_spent": 0,
                    "used_promos": [],
                }
            },
            merge=True,
        )
        logger.info("Initialized credits: %d for user %s", grant, user_doc_ref.id)


def deduct_credits(user_doc_ref: Any, amount: int) -> None:
    """
    Atomically deduct credits from a user.  Balance never goes below 0.

    This is designed to be called from a background thread so it never
    blocks the response flow.

    Args:
        user_doc_ref: Firestore DocumentReference.
        amount: Number of credits to deduct.
    """
    if not user_doc_ref or amount <= 0:
        return

    try:
        # Read current balance to ensure we don't go negative
        doc = user_doc_ref.get()
        if not doc.exists:
            return

        current_balance = doc.to_dict().get("credits", {}).get("balance", 0)
        actual_deduction = min(amount, current_balance)

        if actual_deduction <= 0:
            return

        user_doc_ref.update(
            {
                "credits.balance": transforms.Increment(-actual_deduction),
                "credits.total_spent": transforms.Increment(actual_deduction),
            }
        )
        logger.info(
            "💳 Deducted %d credits (requested %d) from user %s. Remaining: ~%d",
            actual_deduction,
            amount,
            user_doc_ref.id,
            current_balance - actual_deduction,
        )
    except Exception:
        logger.exception("Failed to deduct credits from user %s", user_doc_ref.id)


def deduct_credits_async(user_doc_ref: Any, amount: int) -> None:
    """Fire-and-forget credit deduction in a background thread."""
    threading.Thread(
        target=deduct_credits,
        args=(user_doc_ref, amount),
        daemon=True,
    ).start()


def add_credits(user_doc_ref: Any, amount: int) -> None:
    """
    Add credits to a user's balance.

    Args:
        user_doc_ref: Firestore DocumentReference.
        amount: Number of credits to add.
    """
    if not user_doc_ref or amount <= 0:
        return

    try:
        user_doc_ref.update(
            {"credits.balance": transforms.Increment(amount)}
        )
        logger.info("💳 Added %d credits to user %s", amount, user_doc_ref.id)
    except Exception:
        logger.exception("Failed to add credits to user %s", user_doc_ref.id)


def calculate_grounding_cost(grounding_count: int) -> int:
    """
    Calculate the credit cost for a number of grounded sub-agent prompts.

    Grounding is billed per prompt at a flat USD rate, converted to credits
    using the same EUR conversion and markup as token costs.

    Args:
        grounding_count: How many sub-agent LLM calls triggered Google Search.

    Returns:
        Credit cost (minimum 1 per grounded prompt, 0 if count is 0).
    """
    if grounding_count <= 0:
        return 0
    cost_usd = GROUNDING_COST_PER_PROMPT_USD * grounding_count
    cost_eur = cost_usd * USD_TO_EUR_RATE
    credits = math.ceil(cost_eur * 100 * MARKUP_MULTIPLIER_GROUNDING)
    # Minimum 1 credit per grounded call
    return max(grounding_count, credits)


def calculate_cost(token_records: List[Dict[str, Any]]) -> int:
    """
    Calculate the credit cost for a list of LLM call records.

    Each record is ``{"model_name": str, "input_tokens": int, "output_tokens": int}``.

    Returns:
        Number of credits to deduct (minimum 1 if any tokens were used).
    """
    if not token_records:
        return 0

    total_cost_usd = 0.0
    any_tokens = False
    grounding_credits = 0

    for rec in token_records:
        model = rec.get("model_name", "")

        # Synthetic grounding records carry a pre-calculated credit cost
        if model == "grounding":
            grounding_credits += rec.get("grounding_cost_credits", 0)
            continue

        inp = rec.get("input_tokens", 0)
        out = rec.get("output_tokens", 0)

        if inp == 0 and out == 0:
            continue

        any_tokens = True
        pricing = MODEL_PRICING.get(model, _DEFAULT_PRICING)
        cost = (inp / 1_000_000 * pricing["input"]) + (
            out / 1_000_000 * pricing["output"]
        )
        total_cost_usd += cost

    # Convert token cost to EUR eurocents with markup
    token_credits = 0
    if any_tokens:
        total_cost_eur = total_cost_usd * USD_TO_EUR_RATE
        # Use ceil to ensure we charge at least 1 cent if any significant tokens were used
        token_credits = math.ceil(total_cost_eur * 100 * MARKUP_MULTIPLIER)

    total_credits = token_credits + grounding_credits

    # If no tokens and no grounding, it's truly free (e.g. error or empty)
    if not any_tokens and grounding_credits == 0:
        return 0

    # Ensure at least 1 credit is deducted for any successful LLM interaction
    return max(1, total_credits)


def redeem_promo(
    user_doc: Dict[str, Any],
    user_doc_ref: Any,
    code: str,
) -> Tuple[bool, str, int]:
    """
    Redeem a promo code for a user.

    Args:
        user_doc: The user document dict (for checking used_promos).
        user_doc_ref: Firestore DocumentReference.
        code: The promo code string (case-insensitive).

    Returns:
        Tuple of (success: bool, message: str, credits_added: int).
    """
    normalized = code.strip().upper()

    # Check if code exists
    credit_value = PROMO_CODES.get(normalized)
    if credit_value is None:
        return False, f"❌ Sorry, \"{code}\" is not a valid promo code.", 0

    # Check if already redeemed
    used = user_doc.get("credits", {}).get("used_promos", [])
    if normalized in used:
        return False, f"❌ You've already used the code \"{normalized}\".", 0

    # Apply credits and record usage
    try:
        user_doc_ref.update(
            {
                "credits.balance": transforms.Increment(credit_value),
                "credits.used_promos": transforms.ArrayUnion([normalized]),
            }
        )
        logger.info(
            "🎉 Promo %s redeemed: +%d credits for user %s",
            normalized, credit_value, user_doc_ref.id,
        )
        # Track in weekly metrics (fire-and-forget, in-memory)
        try:
            from agentic_traveler import metrics_tracker
            metrics_tracker.record_promo_redeemed(normalized)
        except Exception:
            logger.exception("Failed to record promo metric for code %s.", normalized)
        return True, (
            f"🎉 Promo code *{normalized}* applied! "
            f"You received *{credit_value} credits* (€{credit_value / 100:.2f})."
        ), credit_value
    except Exception:
        logger.exception("Failed to redeem promo %s for user %s", normalized, user_doc_ref.id)
        return False, "❌ Something went wrong applying the promo code. Please try again.", 0

