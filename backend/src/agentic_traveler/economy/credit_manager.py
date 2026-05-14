"""
Per-user credit management — Supabase backend.

Database layout (``credits`` table, one row per user):
    user_id       : UUID  — FK → users.id
    balance       : INT   — current credit balance (≥ 0)
    initial_grant : INT   — credits given at signup
    total_spent   : INT   — lifetime credits consumed
    used_promos   : TEXT[] — promo codes already redeemed

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

from agentic_traveler.economy.promo_codes import PROMO_CODES

logger = logging.getLogger(__name__)

# ── configuration ──────────────────────────────────────────────────────────

DEFAULT_USER_CREDITS = int(os.getenv("DEFAULT_USER_CREDITS", "500"))
USD_TO_EUR_RATE = float(os.getenv("USD_TO_EUR_RATE", "0.90"))
MARKUP_MULTIPLIER = 3
MARKUP_MULTIPLIER_GROUNDING = 2

# USD per 1 M tokens
MODEL_PRICING: Dict[str, Dict[str, float]] = {
    "gemini-2.5-flash":              {"input": 0.30, "output": 2.50},
    "gemini-2.5-flash-lite":         {"input": 0.10, "output": 0.40},
    "gemini-3.0-flash":              {"input": 0.50, "output": 3.00},
    "gemini-3-flash-preview":        {"input": 0.50, "output": 3.00},
    "gemini-3.1-flash-lite-preview": {"input": 0.10, "output": 0.40},
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


def initialize_credits(user_id: str, amount: Optional[int] = None) -> None:
    """
    Insert the initial credits row for a new user.

    Args:
        user_id: The user's UUID in the ``users`` table.
        amount:  Credits to grant (defaults to DEFAULT_USER_CREDITS).
    """
    from agentic_traveler.tools.db_client import get_db

    grant = amount if amount is not None else DEFAULT_USER_CREDITS
    if not user_id:
        return
    try:
        get_db().table("credits").upsert(
            {
                "user_id": user_id,
                "balance": grant,
                "initial_grant": grant,
                "total_spent": 0,
                "used_promos": [],
            }
        ).execute()
        logger.info("Initialized %d credits for user_id=%s", grant, user_id)
    except Exception:
        logger.exception("Failed to initialize credits for user_id=%s", user_id)


def deduct_credits(user_id: str, amount: int) -> None:
    """
    Deduct credits from a user atomically via a Supabase stored procedure.
    Balance never goes below 0. Uses RPC to avoid a read-then-write race
    condition under concurrent requests.

    Args:
        user_id: The user's UUID.
        amount:  Number of credits to deduct.
    """
    from agentic_traveler.tools.db_client import get_db

    if not user_id or amount <= 0:
        return

    try:
        # The stored procedure handles atomicity and the balance floor at 0.
        resp = get_db().rpc(
            "deduct_credits", {"p_user_id": user_id, "p_amount": amount}
        ).execute()
        new_balance = resp.data if resp and resp.data is not None else "unknown"
        logger.info(
            "💳 Deducted %d credits from user_id=%s. Remaining: %s",
            amount, user_id, new_balance,
        )
    except Exception:
        logger.exception("Failed to deduct credits from user_id=%s", user_id)



def deduct_credits_async(user_id: str, amount: int) -> None:
    """Fire-and-forget credit deduction in a background thread."""
    threading.Thread(
        target=deduct_credits,
        args=(user_id, amount),
        daemon=True,
    ).start()


def add_credits(user_id: str, amount: int) -> None:
    """
    Add credits to a user's balance.

    Args:
        user_id: The user's UUID.
        amount:  Number of credits to add.
    """
    from agentic_traveler.tools.db_client import get_db

    if not user_id or amount <= 0:
        return

    try:
        resp = (
            get_db()
            .table("credits")
            .select("balance")
            .eq("user_id", user_id)
            .maybe_single()
            .execute()
        )
        if not resp.data:
            logger.warning("add_credits: no credits row for user_id=%s", user_id)
            return

        new_balance = resp.data["balance"] + amount
        get_db().table("credits").update(
            {"balance": new_balance}
        ).eq("user_id", user_id).execute()
        logger.info("💳 Added %d credits to user_id=%s", amount, user_id)
    except Exception:
        logger.exception("Failed to add credits to user_id=%s", user_id)


def calculate_grounding_cost(grounding_count: int) -> int:
    """
    Calculate the credit cost for a number of grounded sub-agent prompts.

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

    token_credits = 0
    if any_tokens:
        total_cost_eur = total_cost_usd * USD_TO_EUR_RATE
        token_credits = math.ceil(total_cost_eur * 100 * MARKUP_MULTIPLIER)

    total_credits = token_credits + grounding_credits

    if not any_tokens and grounding_credits == 0:
        return 0

    return max(1, total_credits)


def redeem_promo(
    user_doc: Dict[str, Any],
    user_id: str,
    code: str,
) -> Tuple[bool, str, int]:
    """
    Redeem a promo code for a user.

    Args:
        user_doc: The assembled user dict (for checking used_promos).
        user_id:  The user's UUID.
        code:     The promo code string (case-insensitive).

    Returns:
        Tuple of (success: bool, message: str, credits_added: int).
    """
    from agentic_traveler.tools.db_client import get_db

    normalized = code.strip().upper()

    credit_value = PROMO_CODES.get(normalized)
    if credit_value is None:
        return False, f'❌ Sorry, "{code}" is not a valid promo code.', 0

    used = user_doc.get("credits", {}).get("used_promos", [])
    if normalized in used:
        return False, f'❌ You\'ve already used the code "{normalized}".', 0

    try:
        # Read current balance first
        resp = (
            get_db()
            .table("credits")
            .select("balance, used_promos")
            .eq("user_id", user_id)
            .maybe_single()
            .execute()
        )
        if not resp.data:
            return False, "❌ Could not find your credits record.", 0

        current_balance = resp.data["balance"]
        current_promos = resp.data.get("used_promos") or []

        get_db().table("credits").update(
            {
                "balance": current_balance + credit_value,
                "used_promos": current_promos + [normalized],
            }
        ).eq("user_id", user_id).execute()

        logger.info(
            "🎉 Promo %s redeemed: +%d credits for user_id=%s",
            normalized, credit_value, user_id,
        )
        try:
            from agentic_traveler.analytics import metrics_tracker
            metrics_tracker.record_promo_redeemed(normalized)
        except Exception:
            logger.exception("Failed to record promo metric for code %s.", normalized)

        return True, (
            f"🎉 Promo code *{normalized}* applied! "
            f"You received *{credit_value} credits* (€{credit_value / 100:.2f})."
        ), credit_value
    except Exception:
        logger.exception("Failed to redeem promo %s for user_id=%s", normalized, user_id)
        return False, "❌ Something went wrong applying the promo code. Please try again.", 0
