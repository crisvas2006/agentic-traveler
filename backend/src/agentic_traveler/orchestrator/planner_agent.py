"""
Planner Agent — structured multi-day itinerary builder.

Kept separate from TripAgent because the output format is fundamentally
different: day-by-day blocks with morning/afternoon/evening activities,
logistics, and alternatives. This requires:
  - A dedicated output format enforced by the prompt
  - Higher reasoning demand for multi-day coherence

Google Search grounding is NOT directly enabled — real-time data is
fetched via the SearchAgent proxy (opt-in only).
"""

import logging
import time
from typing import Any, Dict, Optional

from google import genai
from google.genai import types

from agentic_traveler.core.markdown_profile import CANONICAL_FORMATTING
from agentic_traveler.orchestrator.client_factory import get_client, generate_maybe_stream
from agentic_traveler.core.observability import traceable
from agentic_traveler.orchestrator.profile_utils import build_profile_summary
from agentic_traveler.orchestrator.search_agent import SearchAgent
from agentic_traveler.orchestrator.utils import has_grounding, check_weather

logger = logging.getLogger(__name__)

_MODEL = "gemini-3.5-flash"

_SYSTEM_PROMPT = """\
You are a friendly, expert travel planner chatting with a traveler
you know personally.

You understand their personality, preferences, and travel style from
their profile. Use this to make every itinerary feel tailor-made —
not a generic tourist schedule.

PERSONALIZATION RULES (same as Trip Agent):
- Weave preferences into the plan implicitly using descriptive adjectives.
  GOOD: "Tuesday evening at a candlelit trattoria in Trastevere"
        (because you know they love romance — but you don't say that)
  BAD: "Since you prefer romantic settings, I chose Trastevere"
- If they ask WHY something is in the plan, then explain based on
  their specific preferences.
- If preference_updated is provided in the context, acknowledge it naturally.

OUTPUT FORMAT:
- Day-by-day structure using ### headings: "### Day 1 — City Name"
- For each day:
  - **Morning** — one activity (1 line: name + what makes it special)
  - **Afternoon** — one activity (1 line)
  - **Evening** — one activity (1 line)
  - Low-energy alternative for the day (1 line)
- End with: "Want me to adjust anything?"

SAFETY: You may always discuss what the user brings up. If something is
harmful or illegal, gently note a concern while still being helpful.
Never refuse outright — redirect warmly.

CAPABILITIES: You are a planner, not a booking agent. You cannot schedule
private chauffeurs, book flights, reserve hotels, or buy tickets. You ONLY
provide recommendations and itineraries. Never promise to "confirm details,"
"schedule," or "book" something.

WEATHER: For ANY weather question — a direct "how's the weather in X?" or
travel confirmed within the next 10 days — call check_weather(), never
search_web(). It's the authoritative, lower-cost source for weather. Vague
future plans ("plan a trip to Kyoto") don't need it. Adapt activities
naturally; no day-by-day breakdown.

REAL-TIME DATA: For time-sensitive logistics (entry requirements,
seasonal closures, public holiday dates, event schedules) — but NOT weather —
call search_web(); don't guess. Briefly cite sources.

""" + CANONICAL_FORMATTING + """
STRICT LENGTH LIMIT: Never exceed 3500 characters. If the user asks
for "EVERYTHING", provide a curated summary instead.
"""


class PlannerAgent:
    """
    Itinerary builder for PLAN-intent messages.

    Stateless service — initialize once, reuse across parallel requests.
    """

    def __init__(self, client: Optional[genai.Client] = None):
        self._client = client or get_client()
        self._search_agent = SearchAgent(client=self._client)

    @traceable(name="planner_agent.process_request")
    def process_request(
        self,
        user_doc: Dict[str, Any],
        message: str,
        conversation_context: str,
        current_time: str,
        preference_raw: Optional[str] = None,
        events: Optional[Any] = None,
    ) -> Dict[str, Any]:
        """
        Generate a structured day-by-day itinerary.

        Streams token deltas through ``events`` when ``events.is_streaming``
        (web SSE) — itineraries are long, so this is where streaming helps most;
        single synchronous call otherwise (Telegram / non-streaming).

        Returns dict with keys: text, action, _raw_response, _latency_ms,
        _grounding_used.
        """

        # ── execution ────────────────────────────────────────────────────────

        search_responses = []
        search_web = self._search_agent.create_tool(search_responses)

        profile_summary = build_profile_summary(user_doc)

        pref_note = ""
        if preference_raw:
            pref_note = (
                f"\n<preference_updated>\n"
                f"The user just revealed a new preference: "
                f"{preference_raw}\n"
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

        logger.debug("PlannerAgent prompt length: %d chars", len(user_content))
        t = time.time()
        try:
            config = types.GenerateContentConfig(
                system_instruction=_SYSTEM_PROMPT,
                max_output_tokens=8192,
                thinking_config=types.ThinkingConfig(
                    thinking_budget=256,  # tokens
                ),
                automatic_function_calling=types.AutomaticFunctionCallingConfig(
                    maximum_remote_calls=10,  # raised to 10: complex multi-destination itineraries need more searches + weather
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
            )
            response, text = generate_maybe_stream(
                self._client, _MODEL, user_content, config, events,
            )
            latency_ms = (time.time() - t) * 1000
            grounding_used = has_grounding(response)
            return {
                "text": text,
                "action": "PLANNER_RESULTS",
                "_raw_response": response,
                "_search_responses": search_responses,
                "_latency_ms": latency_ms,
                "_grounding_used": grounding_used,
            }
        except Exception:
            logger.exception("PlannerAgent LLM call failed.")
            name = user_doc.get("user_name", "there")
            return {
                "text": f"Sorry {name}, I hit a snag building the itinerary. Please try again.",
                "action": "ERROR",
            }
