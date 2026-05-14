"""
Persists user preference updates to Supabase.

Called by the orchestrator's ``update_preferences`` tool function
when the LLM detects a new preference in the user's message.

No LLM call here — the orchestrator already extracted the key/value
pair through function calling.  This module just handles the
Supabase upsert logic for the ``user_profiles`` table.
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
    "tone_preference",
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
    """Merge and persist a single preference key/value to Supabase."""

    def save_preference(
        self,
        key: str,
        value: str,
        user_doc: Dict[str, Any],
        user_id: str,
        _sync: bool = False,
    ) -> None:
        """
        Persist a preference extracted by the orchestrator by asynchronously
        asking the ProfileAgent to update the structured profile schema.

        Args:
            key:      Preference key (e.g. "budget", "tone_preference").
            value:    Preference value to store.
            user_doc: Current assembled user doc (for reading current profile).
            user_id:  The user's UUID.
            _sync:    If True, update synchronously (useful for tests).
        """
        import threading

        def _async_update():
            try:
                from agentic_traveler.orchestrator.profile_agent import ProfileAgent
                from agentic_traveler.tools.db_client import get_db

                agent = ProfileAgent()
                new_fact = f"The user indicated their '{key}' preference is: {value}"
                current_profile = user_doc.get("user_profile", {})

                updated_structured_data = agent.update_profile(new_fact, current_profile)

                # Upsert the updated profile_data and summary into user_profiles
                get_db().table("user_profiles").upsert(
                    {
                        "user_id": user_id,
                        "profile_data": updated_structured_data,
                        "summary": updated_structured_data.pop("summary", ""),
                    }
                ).execute()

                try:
                    logger.info(
                        "Asynchronously updated profile structure with: %s = %s", key, value
                    )
                except (ValueError, TypeError):
                    pass

            except Exception:
                try:
                    logger.exception("Failed to asynchronously update user profile structure.")
                except (ValueError, TypeError):
                    pass

        if _sync:
            _async_update()
        else:
            thread = threading.Thread(target=_async_update)
            thread.start()
