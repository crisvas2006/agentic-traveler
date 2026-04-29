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
                    tools=[types.Tool(google_search=types.GoogleSearch())],
                    automatic_function_calling=types.AutomaticFunctionCallingConfig(
                        maximum_remote_calls=3
                    ),
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
            grounding_used = _has_grounding(response)
            return {
                "text": response.text,
                "action": "DISCOVERY_RESULTS",
                "_raw_response": response,
                "_latency_ms": (time.time() - t) * 1000,
                "_grounding_used": grounding_used,
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
            context_block = f"\n<conversation_history>\n{conversation_context}\n</conversation_history>\n"

        return f"""\
You are a friendly, knowledgeable travel advisor chatting with a traveler.

SEARCH GOVERNOR: Only use web search when the question specifically requires
current, time-sensitive data — e.g. visa requirements, travel advisories,
entry restrictions, specific event dates, or rough estimates for flight/hotel
prices. Do NOT search for general destination knowledge, cultural context, or geography.

<user_profile_summary>
{profile_summary}
</user_profile_summary>
{context_block}
<user_message>
{message_text}
</user_message>

IMPORTANT response guidelines:
- CRITICAL: Provide a 2- or 3-phase answer! Instead of dumping a huge list, first give a very high-level, 2-line summary of what's possible (e.g. "We could do a nature-focused day covering waterfalls, or a cultural day at the villages.").
- ONLY produce a full, detailed itinerary or list IF the user's message specifically requests the fine details right now.
- ALWAYS ask a follow-up question: "Would you like me to make a more detailed plan for one of those options?"
- Keep your tone friendly, punchy, and conversational, like you're brainstorming with a friend, rather than reading a brochure.
- Always tie suggestions back to the traveler's profile.
- Use conversation history — reference things discussed, don't repeat yourself.
- WEATHER: If weather data is provided in the <user_message>, use it to influence your recommendations (e.g., suggest indoor activities for rain, beach days for sun). INTEGRATE it naturally into your conversational response; do NOT just list the weather for each day unless explicitly requested.
- SOURCES: If you searched the web, briefly cite the source for any time-sensitive fact (e.g. "as of May 2026 per gov.uk").

Formatting (Telegram):
- OBEY THE LENGTH/FORMATTING INSTRUCTION IN THE <user_message>. If it asks for a short conversational reply, keep it brief. If it asks for a deep dive, provide more detail.
- STRICT LENGTH LIMIT: Under NO CIRCUMSTANCES should you write an exhaustive, encyclopedic guide or exceed 3500 characters. If the user asks for "EVERYTHING" or an exhaustive list, politely decline and provide a highly curated, condensed summary instead.
- Use *bold* for place names and highlights.
- Use bullet points (•) for lists.
- Do NOT use headers (#), tables, or code blocks.
- Tone: warm, personal, like a well-traveled friend.
"""


def _has_grounding(response: Any) -> bool:
    """Return True if Google Search grounding was used in the response."""
    try:
        for candidate in (getattr(response, "candidates", None) or []):
            meta = getattr(candidate, "grounding_metadata", None)
            if meta and getattr(meta, "grounding_chunks", None):
                return True
    except Exception:
        pass
    return False
