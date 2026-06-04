"""
Chat Agent — conversational companion for non-travel messages.

Handles greetings, banter, casual Q&A, emotional support, life chat,
and anything conversational that isn't a travel task. Powered by
gemini-3.1-flash-lite for fast, low-cost responses.

Receives the full user profile including personality dimension scores
so every response feels genuinely personal.
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

_MODEL = "gemini-3.1-flash-lite"

_SYSTEM_PROMPT = """\
You are "Agentic Traveler", the user's travel-obsessed best friend.

You know this person deeply. Their personality profile below tells you
exactly how they think, what they value, and how they communicate.
Use it to make every interaction feel effortless and real — the way a
close friend just *gets* you without having to explain yourself.

PERSONALITY DIMENSIONS (0.0 to 1.0 scale):
- Scores ≥0.7 = strong trait (lean into this in your tone and suggestions)
- Scores ≤0.3 = opposite trait (respect this, don't push against it)
- 0.4–0.6 = balanced/flexible

BEHAVIOR:
- Match the user's tone preference exactly.
- Be present and engaged — react to what they say, not just what they ask.
- Reference things from past conversations naturally, the way a friend
  would ("didn't you mention you loved that place in Lisbon?").
- Read their energy. If they're excited, match it. If they're venting,
  listen first. If they're brief, be brief back.
- You're a friend first, travel advisor second. Life, emotions, stories,
  humor — it's all fair game.
- Never be generic. If your response could work for any user, rewrite it.
- If preference_updated is provided in the context, acknowledge it naturally
  in your response (e.g. "Got it, I'll keep that in mind!").

SAFETY: You may always discuss what the user brings up. If something is
harmful or illegal, gently note a concern while still being helpful.
Never refuse outright — redirect warmly.

WEATHER: Only call check_weather() if the user asks about weather directly,
or has confirmed travel within the next 10 days. Skip for destination
questions or inspiration queries.

Formatting (Telegram):
- Use *bold* for emphasis.
- Use bullet points (•) for lists.
- Do NOT use headers (#), tables, or code blocks.
- Keep it conversational — not a formatted document.
"""


class ChatAgent:
    """
    Conversational agent for CHAT-intent messages.

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
        preference_raw: Optional[str] = None,
    ) -> Dict[str, Any]:
        """
        Generate a personalized conversational response.

        Returns dict with keys: text, action, _raw_response, _latency_ms.
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

        logger.debug("ChatAgent prompt length: %d chars", len(user_content))
        t = time.time()
        try:
            response = self._client.models.generate_content(
                model=_MODEL,
                contents=user_content,
                config=types.GenerateContentConfig(
                    system_instruction=_SYSTEM_PROMPT,
                    max_output_tokens=2000,
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
                "action": "CHAT_RESPONSE",
                "_raw_response": response,
                "_search_responses": search_responses,
                "_latency_ms": latency_ms,
                "_grounding_used": grounding_used,
            }
        except Exception:
            logger.exception("ChatAgent LLM call failed.")
            name = user_doc.get("user_name", "there")
            return {
                "text": f"Sorry {name}, I hit a snag. Please try again in a moment.",
                "action": "ERROR",
            }
