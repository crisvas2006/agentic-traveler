"""
Safety Filter — runs on every agent response before it reaches the user.

Uses Gemini 2.5 Flash-Lite (cheap, fast) to:
  1. Flag clearly illegal or obviously unsafe suggestions  → rewrite them.
  2. Flag safety-sensitive or uncertain content             → append a disclaimer.
  3. Pass safe content through unchanged.

Falls back to a keyword-based heuristic if the LLM call fails.
"""

import logging
import os
from typing import Optional

from dotenv import load_dotenv
from google import genai
from google.genai import types

load_dotenv()

logger = logging.getLogger(__name__)

_SAFETY_DISCLAIMER = (
    "\n\n⚠️ Please verify details and safety before booking "
    "or acting on this suggestion."
)

_SYSTEM_PROMPT = """\
You are a safety reviewer for a travel assistant chatbot.
You receive a response that the chatbot is about to send to the user.

Your job:
1. If the response contains clearly illegal or obviously unsafe suggestions
   (e.g. trespassing, drug use, dangerous stunts), REWRITE the response to
   remove those parts and replace them with a safe alternative. Return the
   full rewritten response.
2. If the response touches safety-sensitive topics (e.g. local laws, health
   risks, extreme sports, solo night walks) but is otherwise fine, return the
   original response AS-IS but append EXACTLY this line at the end:
   "SAFETY_DISCLAIMER_NEEDED"
3. If the response is completely safe, return EXACTLY:
   "SAFE"

Reply with ONLY one of the three options above — nothing else.
"""

# Keywords that hint at safety-sensitive content (used in fallback).
_SENSITIVE_KEYWORDS = [
    "illegal", "drug", "weapon", "danger", "unsafe", "risk",
    "trespass", "cliff", "hitchhik", "alone at night", "unregulated",
]


class SafetyFilter:
    """Screens agent responses for unsafe or sensitive content."""

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

    def filter(self, response_text: str) -> str:
        """
        Return a safe version of *response_text*.

        - Unsafe content is rewritten by the LLM.
        - Sensitive content gets a disclaimer appended.
        - Safe content passes through unchanged.
        """
        if not self.client:
            logger.warning("No API key — using keyword safety fallback.")
            return self._keyword_fallback(response_text)

        try:
            result = self.client.models.generate_content(
                model=self.model_name,
                contents=response_text,
                config=types.GenerateContentConfig(
                    system_instruction=_SYSTEM_PROMPT,
                    temperature=0.0,
                    max_output_tokens=2048,
                ),
            )
            verdict = result.text.strip()

            if verdict == "SAFE":
                return response_text
            if verdict.endswith("SAFETY_DISCLAIMER_NEEDED"):
                return response_text + _SAFETY_DISCLAIMER
            # The LLM rewrote the response — return its version.
            return verdict

        except Exception:
            logger.exception("Safety filter LLM call failed — using fallback.")
            return self._keyword_fallback(response_text)

    # ------------------------------------------------------------------
    # Keyword fallback
    # ------------------------------------------------------------------

    def _keyword_fallback(self, text: str) -> str:
        """Append a disclaimer if any sensitive keyword is detected."""
        text_lower = text.lower()
        if any(kw in text_lower for kw in _SENSITIVE_KEYWORDS):
            return text + _SAFETY_DISCLAIMER
        return text
