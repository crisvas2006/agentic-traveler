from typing import Dict, Any, Optional
import logging
import time
from google import genai
from google.genai import types
from dotenv import load_dotenv
from agentic_traveler.orchestrator.profile_utils import build_profile_summary

load_dotenv()

logger = logging.getLogger(__name__)


class CompanionAgent:
    """
    Agent responsible for in-trip assistance.

    Adapts suggestions to the traveler's current mood, energy,
    weather, and time of day.  Returns 2-3 actionable options
    so the user can pick without replanning from scratch.
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
        Generates contextual in-trip suggestions.
        """
        if not self.client:
            return {
                "text": "I'm sorry, I can't help right now (Missing API Key).",
                "action": "ERROR",
            }

        prompt = self._construct_prompt(user_profile, message_text, conversation_context)
        logger.debug("Companion prompt length: %d chars", len(prompt))

        try:
            t = time.time()
            response = self.client.models.generate_content(
                model=self.model_name,
                contents=prompt,
                config=types.GenerateContentConfig(
                    temperature=0.8,
                    max_output_tokens=3000,
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
                ),
            )
            grounding_used = _has_grounding(response)
            return {
                "text": response.text,
                "action": "COMPANION_RESULTS",
                "_raw_response": response,
                "_latency_ms": (time.time() - t) * 1000,
                "_grounding_used": grounding_used,
            }
        except Exception as e:
            logger.exception("Companion agent LLM call failed.")
            return {
                "text": f"I encountered an error: {str(e)}",
                "action": "ERROR",
            }

    def _construct_prompt(
        self,
        user_profile: Dict[str, Any],
        message_text: str,
        conversation_context: str,
    ) -> str:
        """Build the LLM prompt from user context and current message."""
        profile_summary = build_profile_summary(user_profile)

        context_block = ""
        if conversation_context:
            context_block = f"\n<conversation_history>\n{conversation_context}\n</conversation_history>\n"

        return f"""\
You are a friendly, adaptive travel companion chatting with a traveler
who is currently on a trip.

STRICT SEARCH GOVERNOR: Only use web search if the question EXPLICITLY
requires live, real-time data that cannot be answered from general knowledge:
• Current opening hours for a specific venue
• Live public transport status or disruptions
• Today's local events or festivals
• Current entry/border requirements
• Rough estimates for flight/hotel prices (if requested)
Do NOT search for: food suggestions, cultural context, activity ideas,
mood/energy advice, general travel knowledge, or conversational support.
Most in-trip questions do NOT need web search.

<user_profile_summary>
{profile_summary}
</user_profile_summary>
{context_block}
<user_message>
{message_text}
</user_message>

Suggest 2-3 concrete, actionable options the traveler can do right now.
For each option:
• *Option name* — why it fits their mood/energy (1 line)
• Practical details: rough cost, distance, time needed (1 line)

If they mention tiredness or low energy, prioritise low-effort options.
- SOURCES: If you searched the web, briefly cite the source for any live fact.

Formatting (Telegram):
- OBEY THE LENGTH/FORMATTING INSTRUCTION IN THE <user_message>. 
- Use *bold* for option names.
- Use bullet points (•) for structure.
- Do NOT use headers (#), tables, or code blocks.
- Tone: warm and supportive, like a friend who's been to the place.
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
