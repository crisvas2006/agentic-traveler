"""
Extracts preference updates from user messages and merges them into the
user's Firestore profile.

When the IntentClassifier flags ``has_preference=True``, the orchestrator
calls ``PreferenceLearner.extract_and_save()`` which:

1. Asks the LLM to identify the preference as structured JSON.
2. Maps known fields into ``user_profile`` directly.
3. Stores anything else under ``learned_extras``.
"""

import json
import logging
import os
from typing import Any, Dict, Optional

from dotenv import load_dotenv
from google import genai
from google.genai import types

load_dotenv()

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

_SYSTEM_PROMPT = """\
You are a preference extraction engine for a travel assistant.

The user just said something that contains a personal preference or constraint.
Extract the preference(s) as a JSON object.

Rules:
- Use these specific keys when the preference maps to a known field:
  trip_vibe, absolute_avoidances, travel_budget_style, budget_priority,
  typical_trip_lengths, diet_lifestyle_constraints, travel_deal_breakers,
  travel_motivations, next_trip_outcome_goals, structure_preference,
  solo_travel_comfort, activity_level, daily_rhythm, dream_trip_style,
  extra_notes

- For list-type fields (trip_vibe, absolute_avoidances, travel_deal_breakers,
  travel_motivations, next_trip_outcome_goals, typical_trip_lengths),
  return the value as a list of strings.

- If the preference doesn't fit any known field, put it under a key
  called "other" with a short descriptive sub-key, e.g.:
  {"other": {"preferred_airlines": "low-cost only"}}

- Return ONLY valid JSON, nothing else.

Example input: "I hate crowded beaches and my budget is about 800 euros for 5 days"
Example output: {"absolute_avoidances": ["Crowded beaches"], "budget_priority": "~800 EUR for 5 days"}
"""


class PreferenceLearner:
    """Extracts and persists user preferences from conversational messages."""

    def __init__(
        self,
        client: Optional[genai.Client] = None,
        model_name: str = "gemini-2.5-flash-lite",
    ):
        self.client = client
        self.model_name = model_name

    def extract_and_save(
        self,
        user_msg: str,
        user_doc: Dict[str, Any],
        user_doc_ref,
    ) -> Dict[str, Any]:
        """
        Extract preferences from *user_msg* and merge into Firestore.

        Returns:
            The extracted preferences dict (may be empty on failure).
        """
        extracted = self._extract(user_msg)
        if not extracted:
            return {}

        self._merge_and_save(extracted, user_doc, user_doc_ref)
        return extracted

    # ------------------------------------------------------------------
    # Extraction
    # ------------------------------------------------------------------

    def _extract(self, user_msg: str) -> Dict[str, Any]:
        """Ask the LLM to extract structured preference data."""
        if not self.client:
            logger.warning("No API key — skipping preference extraction.")
            return {}

        try:
            response = self.client.models.generate_content(
                model=self.model_name,
                contents=user_msg,
                config=types.GenerateContentConfig(
                    system_instruction=_SYSTEM_PROMPT,
                    temperature=0.0,
                    max_output_tokens=200,
                ),
            )
            raw = response.text.strip()
            # Strip markdown code fences if present
            if raw.startswith("```"):
                raw = raw.split("\n", 1)[-1].rsplit("```", 1)[0].strip()

            data = json.loads(raw)
            logger.info("Extracted preferences: %s", data)
            return data
        except (json.JSONDecodeError, Exception) as exc:
            logger.warning("Preference extraction failed: %s", exc)
            return {}

    # ------------------------------------------------------------------
    # Merge
    # ------------------------------------------------------------------

    def _merge_and_save(
        self,
        extracted: Dict[str, Any],
        user_doc: Dict[str, Any],
        user_doc_ref,
    ) -> None:
        """
        Merge extracted preferences into the user document.

        - Known fields → merged into ``user_profile``
        - Unknown fields → merged into ``learned_extras``
        """
        profile_updates: Dict[str, Any] = {}
        extras_updates: Dict[str, Any] = {}

        current_profile = user_doc.get("user_profile", {})
        current_extras = user_doc.get("learned_extras", {})

        for key, value in extracted.items():
            if key == "other" and isinstance(value, dict):
                # Overflow → learned_extras
                current_extras.update(value)
                extras_updates = current_extras
            elif key in UPDATABLE_PROFILE_FIELDS:
                # For list fields: merge rather than overwrite
                if isinstance(value, list) and isinstance(
                    current_profile.get(key), list
                ):
                    merged = list(set(current_profile[key] + value))
                    profile_updates[f"user_profile.{key}"] = merged
                else:
                    profile_updates[f"user_profile.{key}"] = value
            else:
                # Unknown non-"other" key → learned_extras
                current_extras[key] = value
                extras_updates = current_extras

        firestore_fields: Dict[str, Any] = {}
        if profile_updates:
            firestore_fields.update(profile_updates)
        if extras_updates:
            firestore_fields["learned_extras"] = extras_updates

        if firestore_fields:
            user_doc_ref.set(firestore_fields, merge=True)
            logger.info("Persisted preference updates: %s", list(firestore_fields.keys()))
