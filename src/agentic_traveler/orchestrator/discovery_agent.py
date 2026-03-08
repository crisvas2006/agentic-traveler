from typing import Dict, Any, Optional
import logging
import time
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
        model_name: str = "gemini-2.5-flash",
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
            t = time.time()
            response = self.client.models.generate_content(
                model=self.model_name,
                contents=prompt,
                config=types.GenerateContentConfig(
                    temperature=0.7,
                    max_output_tokens=4500,
                    safety_settings=[
                        types.SafetySetting(
                            category=c,
                            threshold=types.HarmBlockThreshold.BLOCK_ONLY_HIGH,
                        ) for c in [
                            types.HarmCategory.HARM_CATEGORY_DANGEROUS_CONTENT,
                            types.HarmCategory.HARM_CATEGORY_HARASSMENT,
                            types.HarmCategory.HARM_CATEGORY_HATE_SPEECH,
                            types.HarmCategory.HARM_CATEGORY_SEXUALLY_EXPLICIT,
                        ]
                    ]
                )
            )
            return {
                "text": response.text,
                "action": "DISCOVERY_RESULTS",
                "_raw_response": response,
                "_latency_ms": (time.time() - t) * 1000,
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

<user_message>
{message_text}
</user_message>
{context_block}
Their profile:
{profile_summary}

IMPORTANT response guidelines:
- CRITICAL: Provide a 2- or 3-phase answer! Instead of dumping a huge list, first give a very high-level, 2-line summary of what's possible (e.g. "We could do a nature-focused day covering waterfalls, or a cultural day at the villages.").
- ONLY produce a full, detailed itinerary or list IF the user's message specifically requests the fine details right now.
- ALWAYS ask a follow-up question: "Would you like me to make a more detailed plan for one of those options?"
- Keep your tone friendly, punchy, and conversational, like you're brainstorming with a friend, rather than reading a brochure.
- Always tie suggestions back to the traveler's profile.
- Use conversation history — reference things discussed, don't repeat yourself.

Formatting (Telegram):
- OBEY THE LENGTH/FORMATTING INSTRUCTION IN THE <user_message>. If it asks for a short conversational reply, keep it brief. If it asks for a deep dive, provide more detail.
- STRICT LENGTH LIMIT: Under NO CIRCUMSTANCES should you write an exhaustive, encyclopedic guide or exceed 3500 characters. If the user asks for "EVERYTHING" or an exhaustive list, politely decline and provide a highly curated, condensed summary instead.
- Use *bold* for place names and highlights.
- Use bullet points (•) for lists.
- Do NOT use headers (#), tables, or code blocks.
- Tone: warm, personal, like a well-traveled friend.
"""
