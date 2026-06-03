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
    "gemini-3.5-flash":              {"input": 1.50, "output": 9.00},
    "gemini-3.1-flash-lite":         {"input": 0.25, "output": 1.50},
}

# USD per grounded prompt (flat add-on charge, billed per sub-agent call that
# actually triggers a Google Search during generation)
GROUNDING_COST_PER_PROMPT_USD = 0.035  # $35 / 1,000 prompts

# Fallback if we encounter an unknown model
_DEFAULT_PRICING = {"input": 0.50, "output": 3.00}

# Static hardcoded message for zero-credit users (no LLM call needed)
CREDITS_EXHAUSTED_MSG = (
    "⚠️ You've used all your chat credits! You can still use the other features of the app.\n\n"
    "To keep chatting, top up with credits or use a promo code in user settings in the web app.\n\n"
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

    total_token_credits_raw = 0.0
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
        cost_usd = (inp / 1_000_000 * pricing["input"]) + (
            out / 1_000_000 * pricing["output"]
        )
        cost_eur = cost_usd * USD_TO_EUR_RATE
        
        # Determine markup multiplier: 5x for cheap lite models, 3x for others
        markup = 5 if "lite" in model.lower() else 3
        total_token_credits_raw += cost_eur * 100 * markup

    token_credits = math.ceil(round(total_token_credits_raw, 9)) if any_tokens else 0
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


def record_usage_and_bill(
    *,
    user_id: str,
    token_records: List[Dict[str, Any]],
    default_agent_name: str = "agent",
    run_async: bool = False,
) -> int:
    """
    Consolidates credit billing calculation, atomic database deduction,
    weekly metrics logging, and database usage telemetry updates.

    Args:
        user_id:            Database UUID or telegram ID.
        token_records:      List of LLM usage records.
        default_agent_name: Agent name fallback.
        run_async:          Deduct credits asynchronously if True.

    Returns:
        Total credits deducted.
    """
    if not token_records or not user_id:
        return 0

    from agentic_traveler.analytics import usage_tracker
    resolved_uuid = usage_tracker._resolve_user_uuid(user_id)
    if not resolved_uuid:
        logger.warning("record_usage_and_bill: Could not resolve user UUID for %s", user_id)
        return 0

    # 1. Calculate combined total credit cost and deduct
    total_cost = calculate_cost(token_records)
    if total_cost > 0:
        if run_async:
            deduct_credits_async(resolved_uuid, total_cost)
        else:
            deduct_credits(resolved_uuid, total_cost)

    # 2. Distribute costs proportionally among non-grounding records
    raw_records = []
    for rec in token_records:
        if rec.get("model_name") == "grounding":
            raw_records.append(rec.get("grounding_cost_credits", 0))
        else:
            raw_records.append(calculate_cost([rec]))
    total_raw = sum(raw_records)

    non_grounding_recs = [
        (idx, rec) for idx, rec in enumerate(token_records)
        if rec.get("model_name") != "grounding"
    ]

    share_costs = {}
    if non_grounding_recs:
        for list_idx, (idx, rec) in enumerate(non_grounding_recs):
            share_cost = 0
            if total_raw > 0:
                share_cost = int(total_cost * raw_records[idx] / total_raw)
                if list_idx == len(non_grounding_recs) - 1:
                    share_cost = total_cost - sum(share_costs.values())
            share_costs[idx] = share_cost

    # 3. Record global weekly metrics and telemetry
    from agentic_traveler.analytics import metrics_tracker
    by_agent_model = {}
    for idx, rec in enumerate(token_records):
        model = rec.get("model_name")
        if model == "grounding":
            try:
                metrics_tracker.record_grounding_used()
            except Exception:
                logger.exception("Failed to record grounding metric in metrics_tracker.")
            continue

        rec_agent_name = rec.get("agent_name") or default_agent_name
        key = (rec_agent_name, model)
        if key not in by_agent_model:
            by_agent_model[key] = {
                "input_tokens": 0,
                "output_tokens": 0,
                "cost_credits": 0,
            }
        by_agent_model[key]["input_tokens"] += rec.get("input_tokens", 0)
        by_agent_model[key]["output_tokens"] += rec.get("output_tokens", 0)
        by_agent_model[key]["cost_credits"] += share_costs.get(idx, 0)

    for (rec_agent_name, model), usage in by_agent_model.items():
        try:
            metrics_tracker.record_token_usage(
                agent_name=rec_agent_name,
                model_name=model,
                input_tokens=usage["input_tokens"],
                output_tokens=usage["output_tokens"],
                total_cost_credits=usage["cost_credits"],
            )
        except Exception:
            logger.exception("Failed to record token usage in metrics_tracker.")

    # 4. Group by model and record weekly per-user database telemetry
    by_model = {}
    for rec in token_records:
        model = rec.get("model_name")
        if not model or model == "grounding":
            continue
        if model not in by_model:
            by_model[model] = {
                "input_tokens": 0,
                "output_tokens": 0,
                "grounding_used": False,
            }
        by_model[model]["input_tokens"] += rec.get("input_tokens", 0)
        by_model[model]["output_tokens"] += rec.get("output_tokens", 0)
        if rec.get("grounding_used"):
            by_model[model]["grounding_used"] = True

    model_share_costs = {}
    for idx, rec in enumerate(token_records):
        model = rec.get("model_name")
        if not model or model == "grounding":
            continue
        model_share_costs[model] = model_share_costs.get(model, 0) + share_costs.get(idx, 0)

    from agentic_traveler.tools.db_client import get_db
    for model, usage in by_model.items():
        try:
            get_db().rpc("accumulate_user_usage", {
                "p_user_id": resolved_uuid,
                "p_model_name": model,
                "p_input_tokens": usage["input_tokens"],
                "p_output_tokens": usage["output_tokens"],
                "p_is_grounded": 1 if usage["grounding_used"] else 0,
                "p_cost_credits": model_share_costs.get(model, 0)
            }).execute()
        except Exception:
            logger.warning(
                "Telemetry warning: Failed to accumulate usage in usage_tracking table "
                "for user_id=%s model=%s.",
                resolved_uuid, model, exc_info=True
            )

    return total_cost

