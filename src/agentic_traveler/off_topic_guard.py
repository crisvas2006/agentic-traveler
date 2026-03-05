"""
Off-topic guard — tracks consecutive off-topic messages per user.

Persists the counter in the Firestore user document so it survives
container restarts.  After THRESHOLD consecutive off-topic messages
the user is restricted for RESTRICT_SECONDS.

Firestore fields (under each user doc):
    off_topic.count           — consecutive off-topic message count
    off_topic.last_flagged_ts — ISO timestamp of the last off-topic flag
    off_topic.restricted_until — ISO timestamp when restriction lifts (or null)
"""

import logging
from datetime import datetime, timedelta, timezone
from typing import Any, Dict, Optional

logger = logging.getLogger(__name__)

THRESHOLD = 5
RESTRICT_SECONDS = 3600  # 1 hour
# Counter auto-resets if no off-topic flag within this window.
RESET_WINDOW_SECONDS = 3600  # 1 hour


def is_restricted(user_doc: Dict[str, Any]) -> Optional[str]:
    """
    Check if a user is currently restricted.

    Args:
        user_doc: The Firestore user document dict.

    Returns:
        A restriction message string, or None if not restricted.
    """
    off_topic = user_doc.get("off_topic", {})
    restricted_until_str = off_topic.get("restricted_until")

    if not restricted_until_str:
        return None

    try:
        restricted_until = datetime.fromisoformat(restricted_until_str)
    except (ValueError, TypeError):
        return None

    now = datetime.now(timezone.utc)
    if now < restricted_until:
        remaining = restricted_until - now
        minutes = int(remaining.total_seconds() // 60)
        time_str = restricted_until.strftime("%H:%M UTC")
        return (
            f"⛔ Sorry, your access is restricted until {time_str} "
            f"(~{minutes} min remaining) because of repeated off-topic "
            f"messages. This is a travel assistant — I'll be happy to "
            f"help with travel when the restriction lifts!"
        )

    # Restriction expired
    return None


def record_off_topic(
    user_doc: Dict[str, Any], user_doc_ref: Any
) -> Dict[str, Any]:
    """
    Record an off-topic message and persist to Firestore.

    Increments the consecutive counter.  If the counter hits THRESHOLD,
    sets a restriction until now + RESTRICT_SECONDS.

    Also handles the time-based auto-reset: if the last off-topic flag
    was more than RESET_WINDOW_SECONDS ago, resets the counter first.

    Args:
        user_doc: The Firestore user document dict.
        user_doc_ref: Firestore DocumentReference for the user.

    Returns:
        Dict with "count", "restricted", and optionally "restricted_until".
    """
    off_topic = user_doc.get("off_topic", {})
    count = off_topic.get("count", 0)
    last_flagged_str = off_topic.get("last_flagged_ts")

    now = datetime.now(timezone.utc)

    # Auto-reset if the last flag was more than RESET_WINDOW_SECONDS ago
    if last_flagged_str:
        try:
            last_flagged = datetime.fromisoformat(last_flagged_str)
            elapsed = (now - last_flagged).total_seconds()
            if elapsed > RESET_WINDOW_SECONDS:
                logger.info(
                    "Off-topic counter auto-reset (last flag was %.0fs ago).",
                    elapsed,
                )
                count = 0
        except (ValueError, TypeError):
            count = 0

    count += 1

    update: Dict[str, Any] = {
        "off_topic.count": count,
        "off_topic.last_flagged_ts": now.isoformat(),
    }

    result: Dict[str, Any] = {"count": count, "restricted": False}

    if count >= THRESHOLD:
        restricted_until = now + timedelta(seconds=RESTRICT_SECONDS)
        update["off_topic.restricted_until"] = restricted_until.isoformat()
        result["restricted"] = True
        result["restricted_until"] = restricted_until.isoformat()
        logger.warning(
            "User restricted until %s (off-topic count: %d).",
            restricted_until.isoformat(), count,
        )
    else:
        remaining = THRESHOLD - count
        logger.info(
            "Off-topic count: %d/%d (%d remaining before restriction).",
            count, THRESHOLD, remaining,
        )

    # Persist to Firestore
    if user_doc_ref:
        user_doc_ref.set(update, merge=True)

    return result


def reset(user_doc_ref: Any) -> None:
    """
    Reset the off-topic counter (called when user sends a travel message).

    Only resets count and clears restriction — preserves last_flagged_ts
    for analytics.

    Args:
        user_doc_ref: Firestore DocumentReference for the user.
    """
    if user_doc_ref:
        user_doc_ref.set(
            {
                "off_topic.count": 0,
                "off_topic.restricted_until": None,
            },
            merge=True,
        )
