from typing import Dict, Any, List, Optional
import logging
import os
from google import genai
from google.genai import types
from dotenv import load_dotenv
from agentic_traveler.orchestrator.profile_utils import build_profile_summary

load_dotenv()

logger = logging.getLogger(__name__)


class DiscoveryAgent:
    """
    Agent responsible for discovering potential destinations based on user profile and constraints.
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
        Generates destination proposals.
        """
        if not self.client:
            return {
                "text": "I'm sorry, I can't generate travel ideas right now (Missing API Key).",
                "action": "ERROR"
            }

        prompt = self._construct_prompt(user_profile, message_text, conversation_context)
        logger.debug("Discovery prompt length: %d chars", len(prompt))
        
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
                "action": "DISCOVERY_RESULTS"
            }
        except Exception as e:
            logger.exception("Discovery agent LLM call failed.")
            return {
                "text": f"I encountered an error generating ideas: {str(e)}",
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
You are a friendly, knowledgeable travel advisor chatting with a traveler.

The traveler says: "{message_text}"
{context_block}
Their profile:
{profile_summary}

IMPORTANT response guidelines:
- Match the depth of your answer to the user's message.
  If they are just pondering or casually mentioning a place, give a SHORT
  conversational reply (2-4 sentences) with a light suggestion and ask a
  follow-up question to understand their needs better.
- Only produce a full destination list (up to 3 options) when the user
  clearly asks for destination recommendations or gives concrete constraints
  (dates, budget, duration).
- When giving full recommendations, keep each option to 3-4 lines max.
- Always tie suggestions back to the traveler's profile.
- Use the conversation history to maintain continuity — reference things
  you've already discussed and don't repeat yourself.
- Tone: warm, personal, like a well-traveled friend — not a brochure.
"""
