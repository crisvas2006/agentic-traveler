from typing import Dict, Any, Optional
import logging
import os
from google import genai
from google.genai import types
from dotenv import load_dotenv
from agentic_traveler.orchestrator.profile_utils import build_profile_summary

load_dotenv()

logger = logging.getLogger(__name__)


class PlannerAgent:
    """
    Agent responsible for creating detailed trip itineraries.
    """

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
        """
        Generates a trip itinerary.
        """
        if not self.client:
            return {
                "text": "I'm sorry, I can't generate an itinerary right now (Missing API Key).",
                "action": "ERROR"
            }

        prompt = self._construct_prompt(user_profile, message_text, conversation_context)
        logger.debug("Planner prompt length: %d chars", len(prompt))
        
        try:
            response = self.client.models.generate_content(
                model=self.model_name,
                contents=prompt,
                config=types.GenerateContentConfig(
                    temperature=0.7,
                )
            )
            return {
                "text": response.text,
                "action": "PLANNER_RESULTS"
            }
        except Exception as e:
            logger.exception("Planner agent LLM call failed.")
            return {
                "text": f"I encountered an error planning the trip: {str(e)}",
                "action": "ERROR"
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
You are a friendly, expert travel planner chatting with a traveler.

The traveler says: "{message_text}"
{context_block}
Their profile:
{profile_summary}

Create a flexible day-by-day itinerary tailored to this person's style and
energy level.  Keep it concise — use bullet points, not paragraphs.
For each day include:
- A morning, afternoon, and evening suggestion.
- One low-energy alternative per day.
- Use the conversation history for context (destination, dates, preferences
  discussed earlier).
- Keep the total response under 300 words.
- Tone: practical and warm, like a friend who knows the place well.
"""
