"""
Trip Agent — travel discovery and in-trip companion.

Merges the responsibilities of the former DiscoveryAgent and CompanionAgent.
Handles all travel-specific tasks that don't require a structured itinerary:
destination suggestions, in-trip help, travel advice, comparisons.

Uses gemini-3-flash-preview. Google Search grounding is NOT directly enabled —
real-time data is fetched via the SearchAgent proxy (opt-in only).
"""

import logging
import time
from typing import Any, Dict, Optional

from google import genai
from google.genai import types

from agentic_traveler.orchestrator.client_factory import get_client
from agentic_traveler.orchestrator.profile_utils import build_profile_summary
from agentic_traveler.orchestrator.search_agent import SearchAgent
from agentic_traveler.orchestrator.utils import has_grounding, check_weather

logger = logging.getLogger(__name__)

_MODEL = "gemini-3-flash-preview"

_SYSTEM_PROMPT = """\
You are a friendly, deeply knowledgeable travel advisor chatting with
a traveler you know personally.

You understand their personality, preferences, and travel style from
their profile. Use this knowledge to make every suggestion feel natural
and human — as if you instinctively know what they'd love.

PERSONALIZATION RULES:
- Weave their preferences into suggestions implicitly, not explicitly.
  GOOD: "There's a stunning little gallery tucked away in the old town"
        (because you know they love art — but you don't say that)
  BAD: "Since you mentioned you don't like Banksy, I'll skip street art"
        (never name-drop specific preferences as justifications)
- Use descriptive adjectives that align with their vibe (romantic,
  adventurous, serene) — these feel natural.
- If they ask WHY you suggested something, then it is fine to reference
  their specific preferences explicitly.
- If preference_updated is provided in the context, acknowledge it naturally
  in your response.

BEHAVIOR:
- Give a 2-3 option high-level summary first, then ask if they want details.
- For in-trip help: prioritize actionable, immediate options.
- For discovery: be creative but grounded in what you know about them.
- Use conversation history — reference things discussed, don't repeat.

SAFETY: You may always discuss what the user brings up. If something is
harmful or illegal, gently note a concern while still being helpful.
Never refuse outright — redirect warmly.

WEATHER: If you are suggesting activities or plans within the next 10 days,
proactively call check_weather() to inform your recommendations.
Integrate weather naturally (e.g. "looks like clear skies Tuesday,
perfect for that coastal hike"). Do NOT dump a day-by-day weather list.

REAL-TIME DATA: When you need current facts (visa rules, event dates,
prices, opening hours), call search_web() — don't guess.

Formatting (Telegram):
- STRICT LENGTH LIMIT: Never exceed 3500 characters. Curate, don't dump.
- Use *bold* for place names and highlights.
- Use bullet points (•) for lists.
- Do NOT use headers (#), tables, or code blocks.
- Tone: warm, personal, like a well-traveled friend.
"""


class TripAgent:
    """
    Travel agent for TRIP-intent messages.

    Stateless service — initialize once, reuse across parallel requests.
    """

    def __init__(self, client: Optional[genai.Client] = None):
        self._client = client or get_client()
        self._search_agent = SearchAgent(client=self._client)

    def process_request(
        self,
        user_doc: Dict[str, Any],
        message: str,
        conversation_context: str,
        current_time: str,
        preference_updated: Optional[Dict[str, str]] = None,
    ) -> Dict[str, Any]:
        """
        Generate a personalized travel suggestion or in-trip response.

        Returns dict with keys: text, action, _raw_response, _latency_ms,
        _grounding_used.
        """

        # ── execution ────────────────────────────────────────────────────────

        search_responses = []
        search_web = self._search_agent.create_tool(search_responses)

        profile_summary = build_profile_summary(user_doc)

        pref_note = ""
        if preference_updated:
            pref_note = (
                f"\n<preference_updated>\n"
                f"The user just revealed a new preference: "
                f"{preference_updated.get('key')} = {preference_updated.get('value')}\n"
                f"Acknowledge this naturally in your response.\n"
                f"</preference_updated>\n"
            )

        user_content = (
            f"<current_time>{current_time}</current_time>\n"
            f"<user_profile_summary>\n{profile_summary}\n</user_profile_summary>\n"
            f"<conversation_history>\n{conversation_context}\n</conversation_history>\n"
            f"{pref_note}"
            f"<user_message>\n{message}\n</user_message>"
        )

        logger.debug("TripAgent prompt length: %d chars", len(user_content))
        t = time.time()
        try:
            response = self._client.models.generate_content(
                model=_MODEL,
                contents=user_content,
                config=types.GenerateContentConfig(
                    system_instruction=_SYSTEM_PROMPT,
                    temperature=0.7,
                    max_output_tokens=3500,
                    thinking_config=types.ThinkingConfig(
                        thinking_budget=512,  # tokens
                    ),
                    automatic_function_calling=types.AutomaticFunctionCallingConfig(
                        maximum_remote_calls=3,
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
                    ],
                    tools=[check_weather, search_web],
                ),
            )
            latency_ms = (time.time() - t) * 1000
            grounding_used = has_grounding(response)
            return {
                "text": response.text or "",
                "action": "TRIP_RESULTS",
                "_raw_response": response,
                "_search_responses": search_responses,
                "_latency_ms": latency_ms,
                "_grounding_used": grounding_used,
            }
        except Exception:
            logger.exception("TripAgent LLM call failed.")
            name = user_doc.get("user_name", "there")
            return {
                "text": f"Sorry {name}, I hit a snag. Please try again in a moment.",
                "action": "ERROR",
            }
