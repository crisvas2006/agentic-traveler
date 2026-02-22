"""
Chat agent for general conversation (greetings, profile questions, etc.).

Handles anything not classified as NEW_TRIP, PLANNING, or IN_TRIP.
Uses the LLM with the user's full profile so it can answer questions
like "what do you know about me?" properly.
"""

import logging
from typing import Dict, Any, Optional
import os
from google import genai
from google.genai import types
from dotenv import load_dotenv
from agentic_traveler.orchestrator.profile_utils import build_profile_summary

load_dotenv()

logger = logging.getLogger(__name__)


class ChatAgent:
    """Handles general chat — greetings, profile queries, travel Q&A."""

    def __init__(
        self,
        client: Optional[genai.Client] = None,
        model_name: str = "gemini-3-flash-preview",
    ):
        self.client = client
        self.model_name = model_name

    def process_request(
        self,
        user_profile: Dict[str, Any],
        message_text: str,
        conversation_context: str = "",
    ) -> Dict[str, Any]:
        """Generate a conversational reply using the user's profile."""
        if not self.client:
            name = user_profile.get("user_name", "Traveler")
            return {
                "text": f"Hello {name}! How can I help you with your travels today?",
                "action": "CHAT_REPLY",
            }

        prompt = self._construct_prompt(user_profile, message_text, conversation_context)
        logger.debug("Chat prompt length: %d chars", len(prompt))

        try:
            response = self.client.models.generate_content(
                model=self.model_name,
                contents=prompt,
                config=types.GenerateContentConfig(temperature=0.8),
            )
            return {"text": response.text, "action": "CHAT_REPLY"}
        except Exception as e:
            logger.exception("Chat agent LLM call failed.")
            name = user_profile.get("user_name", "Traveler")
            return {
                "text": f"Hello {name}! How can I help you with your travels today?",
                "action": "CHAT_REPLY",
            }

    def _construct_prompt(
        self,
        user_profile: Dict[str, Any],
        message_text: str,
        conversation_context: str,
    ) -> str:
        profile_summary = build_profile_summary(user_profile)

        context_block = ""
        if conversation_context:
            context_block = f"\nConversation so far:\n{conversation_context}\n"

        return f"""\
You are "Agentic Traveler", a friendly AI travel companion.

The traveler says: "{message_text}"
{context_block}
Their full profile:
{profile_summary}

Guidelines:
- If they ask what you know about them, share ALL the information from
  their profile in a warm, conversational way.  Don't skip fields — list
  everything: vibes, avoidances, budget, personality, past trips, diet,
  goals, dream trip, deal breakers, extra notes, and any agent-learned
  preferences.  Organise it naturally (not as raw field names).
- If they ask about past conversations, use the conversation history
  summary to give them a thorough recap.
- If they say hello or thanks, respond warmly and briefly.
- If they ask a general travel question, answer helpfully but concisely.
- For casual chat, keep responses SHORT — 2-5 sentences.
- Tone: friendly, personal, like a well-traveled friend.
"""
