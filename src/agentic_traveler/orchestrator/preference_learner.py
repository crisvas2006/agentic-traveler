"""
Persists user preference updates to Firestore.

Called by the orchestrator's ``update_preferences`` tool function
when the LLM detects a new preference in the user's message.

No LLM call here — the orchestrator already extracted the key/value
pair through function calling.  This module just handles the
Firestore merge logic.
"""

import logging
from typing import Any, Dict, List

logger = logging.getLogger(__name__)

# Fields in user_profile that the agent is allowed to update directly.
# These mirror the Tally form structure.
UPDATABLE_PROFILE_FIELDS = {
    "trip_vibe",
    "absolute_avoidances",
    "travel_budget_style",
    "budget_priority",
    "typical_trip_lengths",
    "diet_lifestyle_constraints",
    "travel_deal_breakers",
    "travel_motivations",
    "next_trip_outcome_goals",
    "structure_preference",
    "solo_travel_comfort",
    "activity_level",
    "daily_rhythm",
    "dream_trip_style",
    "extra_notes",
}

# Fields that are list-valued and should be merged (not overwritten).
LIST_FIELDS = {
    "trip_vibe",
    "absolute_avoidances",
    "travel_deal_breakers",
    "travel_motivations",
    "next_trip_outcome_goals",
    "typical_trip_lengths",
}


class PreferenceLearner:
    """Merge and persist a single preference key/value to Firestore."""

    def save_preference(
        self,
        key: str,
        value: str,
        user_doc: Dict[str, Any],
        user_doc_ref,
    ) -> None:
        """
        Persist a preference extracted by the orchestrator.

        - Known profile fields → merged into ``user_profile``
        - Unknown keys → stored in ``learned_extras``
        - List fields are merged (not overwritten)
        """
        current_profile = user_doc.get("user_profile", {})
        firestore_update: Dict[str, Any] = {}

        if key in UPDATABLE_PROFILE_FIELDS:
            if key in LIST_FIELDS:
                # Merge into existing list
                existing: List[str] = current_profile.get(key, [])
                if isinstance(existing, list):
                    merged = list(set(existing + [value]))
                else:
                    merged = [value]
                firestore_update[f"user_profile.{key}"] = merged
            else:
                firestore_update[f"user_profile.{key}"] = value
        else:
            # Unknown key → learned_extras
            current_extras = user_doc.get("learned_extras", {})
            current_extras[key] = value
            firestore_update["learned_extras"] = current_extras

        if firestore_update:
            user_doc_ref.set(firestore_update, merge=True)
            logger.info("Persisted preference: %s = %s", key, value)
