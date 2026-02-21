"""
Chat agent for general conversation (greetings, profile questions, etc.).

Handles anything not classified as NEW_TRIP, PLANNING, or IN_TRIP.
Uses the LLM with the user's full profile so it can answer questions
like "what do you know about me?" properly.
"""

from typing import Dict, Any, Optional
import os
from google import genai
from google.genai import types
from dotenv import load_dotenv
from agentic_traveler.orchestrator.profile_utils import build_profile_summary

load_dotenv()


class ChatAgent:
    """Handles general chat — greetings, profile queries, travel Q&A."""

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
        """Generate a conversational reply using the user's profile."""
        if not self.client:
            # Graceful fallback when no API key is available
            name = user_profile.get("user_name", "Traveler")
            return {
                "text": f"Hello {name}! How can I help you with your travels today?",
                "action": "CHAT_REPLY",
            }

        prompt = self._construct_prompt(user_profile, message_text)

        try:
            response = self.client.models.generate_content(
                model=self.model_name,
                contents=prompt,
                config=types.GenerateContentConfig(temperature=0.8),
            )
            return {"text": response.text, "action": "CHAT_REPLY"}
        except Exception as e:
            name = user_profile.get("user_name", "Traveler")
            return {
                "text": f"Hello {name}! How can I help you with your travels today?",
                "action": "CHAT_REPLY",
            }

    def _construct_prompt(
        self, user_profile: Dict[str, Any], message_text: str
    ) -> str:
        profile_summary = build_profile_summary(user_profile)

        return f"""\
You are "Agentic Traveler", a friendly AI travel companion.

The traveler says: "{message_text}"

Their profile:
{profile_summary}

Guidelines:
- If they ask what you know about them, summarise their profile naturally
  (don't just dump raw fields — weave it into a warm, conversational answer).
- If they say hello or thanks, respond warmly and briefly.
- If they ask a general travel question, answer helpfully but concisely.
- Keep responses SHORT — 2-5 sentences for casual chat.
- Tone: friendly, personal, like a well-traveled friend.
"""
