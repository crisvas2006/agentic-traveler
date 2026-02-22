"""
LLM-based intent classifier using a cheap, fast model (Gemini 2.5 Flash-Lite).

Returns a tuple of ``(intent, has_preference_update)`` so the orchestrator
can decide whether to run the preference learner without an extra LLM call.
Falls back to keyword heuristics if the LLM is unavailable.
"""

import logging
import os
from typing import Optional, Tuple

from dotenv import load_dotenv
from google import genai
from google.genai import types

load_dotenv()

logger = logging.getLogger(__name__)

# The set of valid intents the classifier may return.
VALID_INTENTS = {"NEW_TRIP", "PLANNING", "IN_TRIP", "CHAT"}

# System prompt — asks for intent + preference flag in one shot.
_SYSTEM_PROMPT = """\
You are an intent classifier for a travel assistant chatbot.
Given the user message, reply with EXACTLY ONE line in the format:

INTENT|PREF_FLAG

Where:
- INTENT is one of: NEW_TRIP, PLANNING, IN_TRIP, CHAT
  NEW_TRIP   – the user wants to discover or explore new destinations
  PLANNING   – the user wants to create or refine an itinerary / schedule
  IN_TRIP    – the user is currently travelling and needs live suggestions
  CHAT       – general conversation, greetings, or anything else

- PREF_FLAG is one of: PREF, NO_PREF
  PREF    – the message reveals or changes a personal preference
            (budget, vibe, avoidance, dietary need, travel style, etc.)
  NO_PREF – no preference information detected

Examples:
"I hate crowded beaches" → CHAT|PREF
"Plan my Rome trip for April" → PLANNING|NO_PREF
"Actually my budget is about 800 euros" → CHAT|PREF
"I want somewhere tropical" → NEW_TRIP|PREF
"Hello!" → CHAT|NO_PREF
"""


class IntentClassifier:
    """Classifies user messages into intent + preference flag."""

    def __init__(
        self,
        client: Optional[genai.Client] = None,
        model_name: str = "gemini-2.5-flash-lite",
    ):
        self.client = client
        self.model_name = model_name

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def classify(self, text: str) -> Tuple[str, bool]:
        """
        Return ``(intent, has_preference_update)`` for *text*.

        Falls back to keyword heuristics (with ``has_preference=False``)
        if the LLM call fails.
        """
        if not self.client:
            logger.warning("No API key — falling back to keyword heuristics.")
            return self._keyword_fallback(text), False

        try:
            response = self.client.models.generate_content(
                model=self.model_name,
                contents=text,
                config=types.GenerateContentConfig(
                    system_instruction=_SYSTEM_PROMPT,
                    temperature=0.0,
                    max_output_tokens=15,
                ),
            )
            raw = response.text.strip().upper()
            return self._parse_response(raw, text)
        except Exception:
            logger.exception("Intent classification LLM call failed.")
            return self._keyword_fallback(text), False

    # ------------------------------------------------------------------
    # Parsing
    # ------------------------------------------------------------------

    def _parse_response(self, raw: str, original_text: str) -> Tuple[str, bool]:
        """Parse the 'INTENT|PREF_FLAG' response from the LLM."""
        parts = [p.strip() for p in raw.split("|")]

        intent = parts[0] if parts else ""
        pref_flag = parts[1] if len(parts) > 1 else "NO_PREF"

        if intent not in VALID_INTENTS:
            logger.warning(
                "LLM returned unexpected intent '%s' — using fallback.", intent
            )
            intent = self._keyword_fallback(original_text)

        has_pref = pref_flag == "PREF"
        logger.info("Classified: intent=%s, has_pref=%s (raw=%s)", intent, has_pref, raw)
        return intent, has_pref

    # ------------------------------------------------------------------
    # Keyword fallback (kept as safety net)
    # ------------------------------------------------------------------

    @staticmethod
    def _keyword_fallback(text: str) -> str:
        """Simple keyword-based intent classification."""
        text_lower = text.lower()
        if any(w in text_lower for w in ("itinerary", "schedule", "detailed plan")):
            return "PLANNING"
        if any(w in text_lower for w in ("plan", "trip", "go to", "visit", "vacation")):
            return "NEW_TRIP"
        if any(w in text_lower for w in ("here", "now", "tired", "hungry", "bored")):
            return "IN_TRIP"
        return "CHAT"
