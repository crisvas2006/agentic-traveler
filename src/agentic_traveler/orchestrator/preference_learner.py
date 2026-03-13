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
    """Merge and persist a single preference key/value to Firestore."""

    def save_preference(
        self,
        key: str,
        value: str,
        user_doc: Dict[str, Any],
        user_doc_ref,
        _sync: bool = False,
    ) -> None:
        """
        Persist a preference extracted by the orchestrator by asynchronously
        asking the ProfileAgent to update the structured profile schema.
        
        Set _sync=True for testing.
        """
        import threading
        
        def _async_update():
            try:
                from agentic_traveler.orchestrator.profile_agent import ProfileAgent
                agent = ProfileAgent()
                
                # Combine key/value into a single natural language fact for the agent
                new_fact = f"The user indicated their '{key}' preference is: {value}"
                
                # We only need to pass the user_profile object to the updater
                current_profile = user_doc.get("user_profile", {})
                
                updated_structured_data = agent.update_profile(new_fact, current_profile)
                
                # Merge the updated scores, tags, additional_info, and summary back
                user_doc_ref.set({"user_profile": updated_structured_data}, merge=True)
                
                # Use a try-except to avoid "I/O operation on closed file" when exiting
                try:
                    logger.info("Asynchronously updated profile structure with: %s = %s", key, value)
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
            # Fire and forget; doesn't block the LLM response to the user
            thread = threading.Thread(target=_async_update)
            thread.start()
