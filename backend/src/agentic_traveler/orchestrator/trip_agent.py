"""
Trip Agent — travel discovery and in-trip companion.

Merges the responsibilities of the former DiscoveryAgent and CompanionAgent.
Handles all travel-specific tasks that don't require a structured itinerary:
destination suggestions, in-trip help, travel advice, comparisons.

Uses gemini-3.5-flash. Google Search grounding is NOT directly enabled —
real-time data is fetched via the SearchAgent proxy (opt-in only).
"""

import logging
import time
from typing import Any, Dict, Optional

from google import genai
from google.genai import types

from agentic_traveler.core.markdown_profile import CANONICAL_FORMATTING
from agentic_traveler.core.budget_policy import (
    build_voice_block,
    handle_finish_reason,
    resolve as budget_resolve,
)
from agentic_traveler.orchestrator.client_factory import get_client, generate_maybe_stream
from agentic_traveler.core.observability import traceable
from agentic_traveler.orchestrator.profile_utils import build_profile_summary
from agentic_traveler.orchestrator.search_agent import SearchAgent
from agentic_traveler.orchestrator.utils import has_grounding, check_weather

logger = logging.getLogger(__name__)

_MODEL = "gemini-3.5-flash"

_SYSTEM_PROMPT_BASE = """\
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

CAPABILITIES: You are an advisor, not a booking agent. You cannot schedule
private chauffeurs, book flights, reserve hotels, or buy tickets. You ONLY
provide recommendations. Never promise to "confirm details," "schedule," or "book" something.

WEATHER: Only call check_weather() when the user has confirmed travel within
the next 10 days (specific date, "this weekend", "leaving Friday"). Skip for
discovery or inspiration queries. Integrate naturally; no day-by-day lists.

REAL-TIME DATA: Only call when you need current facts (visa rules, event dates,
prices, opening hours), call search_web() — don't guess.

""" + CANONICAL_FORMATTING


def _build_system_prompt(char_cap: int) -> str:
    """Build the full system prompt with the anti-bloat voice block injected."""
    return _SYSTEM_PROMPT_BASE + "\n" + build_voice_block(char_cap)


class TripAgent:
    """
    Travel agent for TRIP-intent messages.

    Stateless service — initialize once, reuse across parallel requests.
    """

    def __init__(self, client: Optional[genai.Client] = None):
        self._client = client or get_client()
        self._search_agent = SearchAgent(client=self._client)

    @traceable(name="trip_agent.process_request")
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
        Generate a personalized travel suggestion or in-trip response.

        When ``events.is_streaming`` is True the reply is streamed token-by-token
        through ``events`` (web SSE); otherwise a single synchronous call is made
        (Telegram / non-streaming web). Tool status fires via ``events`` in both.

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

        budget = budget_resolve("trip_companion", user_doc)

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
            config = types.GenerateContentConfig(
                system_instruction=_build_system_prompt(budget.char_cap),
                max_output_tokens=budget.max_tokens_ceiling,
                thinking_config=types.ThinkingConfig(
                    # LOW level (256 tokens) is enough for TRIP tool-orchestration:
                    # decide weather/search, then synthesize. Budget-driven via policy.
                    thinking_budget=budget.thinking_budget,
                ),
                automatic_function_calling=types.AutomaticFunctionCallingConfig(
                    maximum_remote_calls=6,  # raised from 3: trip requests routinely need 2 searches + weather + extras
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

            # AC-4: Handle MAX_TOKENS finish reason gracefully.
            text, ceiling_hit = handle_finish_reason(response, text, "trip_companion")
            if ceiling_hit:
                if events:
                    events.emit("metric", {
                        "name": "token_ceiling_hit",
                        "call_type": "trip_companion",
                    })
                if not text:
                    name = user_doc.get("user_name", "there")
                    return {
                        "text": f"Sorry {name}, I hit a snag. Please try again in a moment.",
                        "action": "ERROR",
                    }

            # AC-5: Emit budget_violation metric if reply is over cap by >15%.
            if text and budget.char_cap > 0 and len(text) > budget.char_cap * 1.15:
                overage_pct = int((len(text) - budget.char_cap) / budget.char_cap * 100)
                if events:
                    events.emit("metric", {
                        "name": "budget_violation",
                        "call_type": "trip_companion",
                        "overage_pct": overage_pct,
                    })

            return {
                "text": text,
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
