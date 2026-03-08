from typing import Dict, Any, Optional
import logging
import time
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
                "action": "PLANNER_RESULTS",
                "_raw_response": response,
                "_latency_ms": (time.time() - t) * 1000,
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

<user_message>
{message_text}
</user_message>
{context_block}
Their profile:
{profile_summary}

Create a flexible day-by-day itinerary tailored to this person's style and
energy level.  For each day include:
• Morning, afternoon, and evening — one line each
• One low-energy alternative per day
Use conversation history for context (destination, dates, preferences).

Formatting (Telegram):
- OBEY THE LENGTH/FORMATTING INSTRUCTION IN THE <user_message>. If it asks for a short summary, provide that. If it asks for a deep dive itinerary, provide full details.
- STRICT LENGTH LIMIT: Under NO CIRCUMSTANCES should you write an exhaustive, encyclopedic guide or exceed 3500 characters. If the user asks for "EVERYTHING" or an exhaustive list, politely decline and provide a highly curated, condensed summary instead.
- Use *bold* for day headings and place names.
- Use numbered lists (1. 2. 3.) for days, bullet points (•) for activities.
- Do NOT use headers (#), tables, or code blocks.
- Keep each activity to one line — name + what makes it special.
- Tone: practical and warm, like a friend who knows the place well.
- End with a brief "Want me to adjust anything?" to invite follow-up.
"""
