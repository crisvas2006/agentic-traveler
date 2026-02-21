"""
LLM-based intent classifier using a cheap, fast model (Gemini 2.5 Flash-Lite).

The classifier asks the model to return a single intent label from a
fixed set.  A keyword-based fallback is kept in case the LLM call
fails or the API key is missing.
"""

import logging
import os
from typing import Optional

from dotenv import load_dotenv
from google import genai
from google.genai import types

load_dotenv()

logger = logging.getLogger(__name__)

# The set of valid intents the classifier may return.
VALID_INTENTS = {"NEW_TRIP", "PLANNING", "IN_TRIP", "CHAT"}

# System prompt — kept very short to minimise token usage.
_SYSTEM_PROMPT = """\
You are an intent classifier for a travel assistant chatbot.
Given the user message, reply with EXACTLY ONE of the following labels and nothing else:

NEW_TRIP   – the user wants to discover or explore new destinations
PLANNING   – the user wants to create or refine an itinerary / schedule
IN_TRIP    – the user is currently travelling and needs live suggestions
CHAT       – general conversation, greetings, or anything else
"""


class IntentClassifier:
    """Classifies user messages into one of the supported intents."""

    def __init__(
        self,
        api_key: Optional[str] = None,
        model_name: str = "gemini-2.5-flash-lite",
    ):
        self.api_key = api_key or os.getenv("GOOGLE_API_KEY")
        self.client = (
            genai.Client(api_key=self.api_key) if self.api_key else None
        )
        self.model_name = model_name

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def classify(self, text: str) -> str:
        """
        Return the intent label for *text*.

        Falls back to keyword heuristics if the LLM call fails.
        """
        if not self.client:
            logger.warning("No API key — falling back to keyword heuristics.")
            return self._keyword_fallback(text)

        try:
            response = self.client.models.generate_content(
                model=self.model_name,
                contents=text,
                config=types.GenerateContentConfig(
                    system_instruction=_SYSTEM_PROMPT,
                    temperature=0.0,
                    max_output_tokens=10,
                ),
            )
            label = response.text.strip().upper()
            if label in VALID_INTENTS:
                return label

            logger.warning(
                "LLM returned unexpected label '%s' — using fallback.", label
            )
            return self._keyword_fallback(text)
        except Exception:
            logger.exception("Intent classification LLM call failed.")
            return self._keyword_fallback(text)

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
