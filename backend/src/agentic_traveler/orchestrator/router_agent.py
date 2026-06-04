"""
Router Agent — lightweight intent classifier and tool executor.

Classifies user messages into CHAT | TRIP | PLAN | OFF_TOPIC and handles
simple tool calls (preference updates, feedback, credits) directly,
without delegating to a heavier specialized agent.

OFF_TOPIC messages: the router generates a natural, warm redirection
response instead of a static string, while the orchestration layer
silently increments the off-topic counter.
"""

import json
import logging
import time
from typing import Any, Dict, Optional

from google import genai
from google.genai import types

from agentic_traveler.orchestrator.client_factory import get_client
from agentic_traveler.orchestrator.profile_agent import ProfileAgent
from agentic_traveler.tools.feedback_tool import FeedbackTool
from agentic_traveler.economy import credit_manager

logger = logging.getLogger(__name__)

_MODEL = "gemini-3.1-flash-lite"
_SYSTEM_PROMPT = """\
You are the intent router for Agentic Traveler, a travel companion chatbot.

Your job: classify the user's message into exactly one intent and extract
the core request. You do NOT generate the final response EXCEPT for OFF_TOPIC messages, where you provide
a natural, friendly redirection yourself in the same language as the user.

INTENTS:
• CHAT — Greetings, thanks, jokes, banter, personal stories, emotional
  support, life advice, opinions, "how are you", compliments, or any
  message that is conversational but not asking for travel-specific help.
  Examples: "hey!", "thanks that was great", "how's your day?",
  "tell me a joke", "I'm feeling stressed"

• TRIP — Any travel-related question, suggestion request, destination
  exploration, in-trip help, "what to do in X", weather questions,
  comparisons between destinations, visa/entry questions, or travel advice.
  This includes both pre-trip research and live in-trip assistance.
  Examples: "what should I do in Bali?", "I'm tired and it's raining",
  "is Lombok worth visiting?", "what's the weather in Rome?",
  "best time to visit Japan?"

• PLAN — An explicit request for a structured, detailed, day-by-day
  itinerary or trip schedule. The user must be asking for organized
  planning with specific days/structure, not just casual suggestions.
  Examples: "plan my 5-day trip to Rome", "make me an itinerary for
  Lombok", "organize my week in Tokyo", "help me plan day by day"

• OFF_TOPIC — The last user message is clearly unrelated to travel AND is not
  casual/fun conversation. Math homework, coding questions, politics, etc.
  BE LENIENT: jokes, banter, personal stories, and life advice are CHAT,
  not OFF_TOPIC.
  When you classify OFF_TOPIC, generate a short, warm, natural redirection
  in the "response" field. Don't be robotic — redirect like a friend would.

Classify the intent. If the user's message warrants calling a tool, call the appropriate tool AND still classify the intent.

CRITICAL: Only call update_preferences (at most once) if the user's LATEST message explicitly states a new/changed preference not listed in Known Preferences.
- Do NOT extract preferences from Conversation Context history.
- Never speculate or extrapolate preferences (e.g. do NOT assume tone_preference="concise" due to a brief message).
- If the latest message is a question, greeting, or feedback, do not call it.
- Always set "preference_raw" in the JSON response to match the exact extracted preference statement, or null.

CRITICAL: The record_feedback tool is ONLY for the current message and if the user is explicitly talking ABOUT THE BOT ITSELF (e.g. "you are a great bot", "this app sucks", "add a dark mode").
Do NOT use it for travel questions, personal statements, frustration with travel, testing, or random gibberish. If you are not 100% sure it is app feedback, DO NOT call it.

CRITICAL: Call get_my_credits ONLY when the current message explicitly asks about credits or balance. Do NOT call it proactively or because credits were mentioned earlier.

Respond ONLY with a JSON object matching this schema:
{{
  "intent": "TRIP|CHAT|PLAN|OFF_TOPIC",
  "request_summary": "one-sentence description of what the user wants",
  "preference_raw": "raw user statement indicating preference, or null",
  "response": "natural redirection text (OFF_TOPIC) OR credit balance info, else null"
}}

Current time: {current_time}
User: {user_name}
Known Preferences: {known_preferences}
Conversation Context: {conversation_context}
"""


class RouterAgent:
    """
    Thin intent router. Classifies messages and handles lightweight tools.

    Stateless service — initialize once, reuse across parallel requests.
    """

    def __init__(self, client: Optional[genai.Client] = None):
        self._client = client or get_client()
        self._profile_agent = ProfileAgent()
        self._feedback_tool = FeedbackTool()

    def classify(
        self,
        message: str,
        user_doc: Dict[str, Any],
        user_id: str,
        telegram_user_id: str,
        user_name: str,
        current_time: str,
        conversation_context: str = "",
        token_records: Optional[list] = None,
    ) -> Dict[str, Any]:
        """
        Classify user intent and handle lightweight tool calls.

        Returns a dict with keys:
            intent: str — CHAT | TRIP | PLAN | OFF_TOPIC
            request_summary: str
            preference_raw: str | None
            response: str | None  — only set for OFF_TOPIC or get_my_credits
            raw_response: the raw genai response (for token logging)
            latency_ms: float
        """

        # ── tool definitions (closures capture user context safely) ──────────

        def update_preferences(preference_raw: str) -> str:
            """
            Persist a newly learned user preference from the user's current message to their profile.

            Call this when the user's CURRENT message reveals a new personal preference
            or changes an existing one (e.g. related to budget, travel style, dietary needs, tone).
            
            CRITICAL: Only call this if the user explicitly states a preference. Never speculate
            or extrapolate tone preferences (like "concise") from brief or short messages.

            Args:
                preference_raw: The exact raw user statement containing the preference.

            Returns:
                Confirmation string.
            """
            logger.info("🔧 Router tool: update_preferences(%s)", preference_raw)
            if user_id:
                self._profile_agent.save_preference(
                    preference_raw,
                    user_doc, user_id,
                    # Do not pass token_records so it executes asynchronously
                )
            return f"Noted preference: {preference_raw}"

        def record_feedback(category: str, text: str) -> str:
            """
            Record an EXPLICIT user feedback signal ABOUT THIS APP to the analytics backend.

            WARNING: ONLY call this if the user is explicitly praising the bot, 
            complaining about the bot's behavior, or suggesting an app feature. 
            DO NOT call this for general conversation, travel frustration, jokes, 
            testing, or random questions. If you are not 100% sure it is app feedback, 
            DO NOT CALL THIS TOOL.

            Args:
                category: EXACTLY one of: positive, negative, suggestion.
                text:     The exact feedback text provided by the user.

            Returns:
                Confirmation string.
            """
            logger.info("🔧 Router tool: record_feedback(category=%s)", category)
            self._feedback_tool.record(
                user_id=user_id,
                text=text,
                category=category,
                user_doc=user_doc,
                _sync=False,
            )
            return "Feedback recorded."

        def get_my_credits() -> str:
            """
            Returns the user's current credit balance.

            Call this ONLY when the user's current message explicitly asks about
            their credits, balance, or remaining uses (e.g. "how many credits do
            I have?", "what's my balance?"). Do NOT call proactively, and do NOT
            call just because credits were mentioned in the conversation history.

            Returns:
                String containing current balance and how credits work.
            """
            logger.info("🔧 Router tool: get_my_credits")
            balance = credit_manager.get_balance(user_doc)
            return (
                f"You have *{balance} credits* remaining. "
                f"Credits are used for AI-powered features like destination discovery, "
                f"itinerary planning, and weather checks. "
                f"Each interaction costs 1 or more credits depending on complexity. "
                f"You can top up with credits or use a promo code in your web app user settings."
            )

        _ = telegram_user_id  # referenced by outer scope, avoids lint warning

        # ── execution ────────────────────────────────────────────────────────

        from agentic_traveler.orchestrator.profile_utils import build_profile_summary
        known_prefs = build_profile_summary(user_doc, include_scores=False, include_summary=True)
        if user_doc.get("language"):
            known_prefs += f"\nLanguage: {user_doc.get('language')}"
        if not known_prefs:
            known_prefs = "None"

        system = _SYSTEM_PROMPT.format(
            current_time=current_time,
            user_name=user_name,
            known_preferences=known_prefs,
            conversation_context=conversation_context,
        )

        t = time.time()
        try:
            raw = self._client.models.generate_content(
                model=_MODEL,
                contents=message,
                config=types.GenerateContentConfig(
                    system_instruction=system,
                    max_output_tokens=256,
                    response_mime_type="application/json",
                    automatic_function_calling=types.AutomaticFunctionCallingConfig(
                        maximum_remote_calls=5,
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
                    tools=[update_preferences, record_feedback, get_my_credits],
                ),
            )
            latency_ms = (time.time() - t) * 1000

            # When AFC executes a tool, the model's last turn is a function_response
            # part, not a text part.  In that case raw.text is None, so json.loads("")
            # raises JSONDecodeError and we lose the entire result.
            # Detect this situation and build the result dict from the parts directly.
            text = raw.text or ""
            preference_raw_from_tool: str | None = None

            # Always try to recover preference_raw from function calls as the primary source or fallback
            try:
                for candidate in (getattr(raw, "candidates", None) or []):
                    for part in (getattr(candidate.content, "parts", None) or []):
                        fc = getattr(part, "function_call", None)
                        if fc and getattr(fc, "name", None) == "update_preferences":
                            args = dict(fc.args or {})
                            preference_raw_from_tool = args.get("preference_raw")
            except Exception:
                pass

            if not text:
                # Cannot determine intent from empty text — default to CHAT so the
                # user still gets a response. The preference update already ran via
                # AFC side effect.
                result = {
                    "intent": "CHAT",
                    "request_summary": message,
                    "preference_raw": preference_raw_from_tool,
                    "response": None,
                }
                logger.info(
                    "Router returned no text (AFC tool-only turn). "
                    "Defaulting intent=CHAT, preference_raw=%s",
                    preference_raw_from_tool,
                )
            else:
                try:
                    result = json.loads(text)
                    # Merge JSON preference_raw with tool extraction if JSON lacks it
                    if not result.get("preference_raw") and preference_raw_from_tool:
                        result["preference_raw"] = preference_raw_from_tool
                except json.JSONDecodeError:
                    logger.warning("Router JSON parse failed. Raw text: %s", text)
                    result = {
                        "intent": "CHAT",
                        "request_summary": message,
                        "preference_raw": preference_raw_from_tool,
                        "response": None,
                    }

            result["raw_response"] = raw
            result["latency_ms"] = latency_ms
            logger.info(
                "Router classified '%s' → %s (%.0fms)",
                message[:60], result.get("intent"), latency_ms,
            )
            return result

        except Exception:
            logger.exception("Router classify failed — defaulting to CHAT.")
            return {
                "intent": "CHAT",
                "request_summary": message,
                "preference_raw": None,
                "response": None,
                "raw_response": None,
                "latency_ms": (time.time() - t) * 1000,
            }
