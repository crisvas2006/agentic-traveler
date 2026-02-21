from typing import Dict, Any, Optional
import os
from google import genai
from google.genai import types
from dotenv import load_dotenv

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
        model_name: str = "gemini-3.1-pro",
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
        user_name = user_profile.get("user_name", "Traveler")
        preferences = user_profile.get("preferences", {})
        avoidances = preferences.get("avoidances", "none specified")
        vibes = preferences.get("vibes", "any")

        return f"""
You are a friendly, adaptive travel companion for '{user_name}'.

The traveler is currently on a trip and says:
"{message_text}"

Their profile highlights:
- Preferred vibes: {vibes}
- Hard avoidances: {avoidances}
- General preferences: {preferences}

Based on the message above, suggest 2-3 concrete, actionable options
the traveler can do right now.  For each option include:
1. A short title
2. Why it fits the traveler's current mood / energy
3. Practical details (rough cost, distance, time needed)

Keep the tone warm and supportive.  If the message mentions tiredness
or low energy, prioritise low-effort options.
"""
