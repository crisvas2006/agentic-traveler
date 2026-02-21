from typing import Dict, Any, Optional
import os
from google import genai
from google.genai import types
from dotenv import load_dotenv
from agentic_traveler.orchestrator.profile_utils import build_profile_summary

load_dotenv()


class CompanionAgent:
    """
    Agent responsible for in-trip assistance.

    Adapts suggestions to the traveler's current mood, energy,
    weather, and time of day.  Returns 2-3 actionable options
    so the user can pick without replanning from scratch.
    """

    def __init__(
        self,
        api_key: Optional[str] = None,
        model_name: str = "gemini-3-flash-preview",
    ):
        self.api_key = api_key or os.getenv("GOOGLE_API_KEY")
        self.client = genai.Client(api_key=self.api_key) if self.api_key else None
        self.model_name = model_name

    def process_request(
        self, user_profile: Dict[str, Any], message_text: str
    ) -> Dict[str, Any]:
        """
        Generates contextual in-trip suggestions.

        Args:
            user_profile: The user's profile from Firestore.
            message_text: The message describing current mood / situation.

        Returns:
            A dict with ``text`` (the suggestions) and ``action``.
        """
        if not self.client:
            return {
                "text": "I'm sorry, I can't help right now (Missing API Key).",
                "action": "ERROR",
            }

        prompt = self._construct_prompt(user_profile, message_text)

        try:
            response = self.client.models.generate_content(
                model=self.model_name,
                contents=prompt,
                config=types.GenerateContentConfig(
                    temperature=0.8,
                ),
            )
            return {
                "text": response.text,
                "action": "COMPANION_RESULTS",
            }
        except Exception as e:
            return {
                "text": f"I encountered an error: {str(e)}",
                "action": "ERROR",
            }

    def _construct_prompt(
        self, user_profile: Dict[str, Any], message_text: str
    ) -> str:
        """Build the LLM prompt from user context and current message."""
        profile_summary = build_profile_summary(user_profile)

        return f"""\
You are a friendly, adaptive travel companion chatting with a traveler
who is currently on a trip.

The traveler says: "{message_text}"

Their profile:
{profile_summary}

Based on the message above, suggest 2-3 concrete, actionable options
the traveler can do right now.  For each option include:
1. A short title
2. Why it fits the traveler's current mood / energy
3. Practical details (rough cost, distance, time needed)

Keep the total response under 200 words.
If the message mentions tiredness or low energy, prioritise low-effort options.
Tone: warm and supportive, like a friend who's been to the place.
"""
