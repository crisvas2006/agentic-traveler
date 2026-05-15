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
from agentic_traveler.orchestrator.preference_learner import PreferenceLearner
from agentic_traveler.tools.feedback_tool import FeedbackTool
from agentic_traveler.economy import credit_manager

logger = logging.getLogger(__name__)

_MODEL = "gemini-3.1-flash-lite-preview"
_SYSTEM_PROMPT = """\
You are the intent router for Agentic Traveler, a travel companion chatbot.

Your job: classify the user's message into exactly one intent and extract
the core request. You do NOT generate the final response — a specialized
agent handles that — EXCEPT for OFF_TOPIC messages, where you provide
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

• OFF_TOPIC — The message is clearly unrelated to travel AND is not
  casual/fun conversation. Math homework, coding questions, politics, etc.
  BE LENIENT: jokes, banter, personal stories, and life advice are CHAT,
  not OFF_TOPIC.
  When you classify OFF_TOPIC, generate a short, warm, natural redirection
  in the "response" field. Don't be robotic — redirect like a friend would.

Classify the intent. If the user's message reveals a NEW preference or CHANGES an existing one,
gives explicit feedback (praise or complaint), or asks about credits remaining,
call the appropriate tool AND still classify the intent.

CRITICAL: Do NOT call update_preferences if the preference is already listed below in your prompt!

CRITICAL: The record_feedback tool is ONLY for when the user is explicitly talking ABOUT THE BOT ITSELF (e.g. "you are a great bot", "this app sucks", "add a dark mode").
Do NOT use it for travel questions, personal statements, frustration with travel, testing, or random gibberish. If you are not 100% sure it is app feedback, DO NOT call it.

Respond ONLY with a JSON object matching this schema:
{{
  "intent": "TRIP|CHAT|PLAN|OFF_TOPIC",
  "request_summary": "one-sentence description of what the user wants",
  "preference_updated": {{"key": "...", "value": "..."}} or null,
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
        self._preference_learner = PreferenceLearner()
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
    ) -> Dict[str, Any]:
        """
        Classify user intent and handle lightweight tool calls.

        Returns a dict with keys:
            intent: str — CHAT | TRIP | PLAN | OFF_TOPIC
            request_summary: str
            preference_updated: dict | None
            response: str | None  — only set for OFF_TOPIC or get_my_credits
            raw_response: the raw genai response (for token logging)
            latency_ms: float
        """

        # ── tool definitions (closures capture user context safely) ──────────

        def update_preferences(preference_key: str, preference_value: str) -> str:
            """
            Persist a NEWLY learned or CHANGED user preference to their profile.

            Call this when the user's CURRENT message reveals a new personal preference
            or changes an existing one (e.g. budget, travel style, dietary needs, tone).
            
            CRITICAL: DO NOT call this tool for preferences that are already known and 
            listed in your system prompt (e.g. if the prompt says 'Tone preference: intense', 
            do not call this to record 'intense' again).
            
            Args:
                preference_key: Short identifier for the preference
                    (e.g. "budget", "avoidances", "diet", "travel_style", "tone_preference").
                preference_value: The preference value to store.

            Returns:
                Confirmation string.
            """
            logger.info("🔧 Router tool: update_preferences(%s=%s)", preference_key, preference_value)
            if user_id:
                self._preference_learner.save_preference(
                    preference_key, preference_value,
                    user_doc, user_id,
                )
            return f"Noted: {preference_key} = {preference_value}"

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

            Call this when the user asks how many credits they have left,
            what their balance is, or anything related to their usage/credit status.

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
                f"You can top up with a promo code via /promo YOUR_CODE."
            )

        _ = telegram_user_id  # referenced by outer scope, avoids lint warning

        # ── execution ────────────────────────────────────────────────────────

        profile_data = user_doc.get("user_profile", {})
        known_prefs_dict = {k: v for k, v in profile_data.items() if isinstance(v, (str, int, bool))}
        if user_doc.get("language"):
            known_prefs_dict["language"] = user_doc.get("language")
        known_prefs = ", ".join(f"{k}: {v}" for k, v in known_prefs_dict.items())
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
                    temperature=0.1,
                    max_output_tokens=256,
                    response_mime_type="application/json",
                    automatic_function_calling=types.AutomaticFunctionCallingConfig(
                        maximum_remote_calls=4,
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
            preference_updated_from_tool: dict | None = None

            if not text:
                # AFC tool-call path: try to recover intent from any function call parts
                try:
                    for candidate in (getattr(raw, "candidates", None) or []):
                        for part in (getattr(candidate.content, "parts", None) or []):
                            fc = getattr(part, "function_call", None)
                            if fc and getattr(fc, "name", None) == "update_preferences":
                                args = dict(fc.args or {})
                                preference_updated_from_tool = {
                                    "key": args.get("preference_key", ""),
                                    "value": args.get("preference_value", ""),
                                }
                except Exception:
                    pass

                # Cannot determine intent from empty text — default to CHAT so the
                # user still gets a response.  The preference update already ran via
                # AFC side effect.
                result = {
                    "intent": "CHAT",
                    "request_summary": message,
                    "preference_updated": preference_updated_from_tool,
                    "response": None,
                }
                logger.info(
                    "Router returned no text (AFC tool-only turn). "
                    "Defaulting intent=CHAT, preference_updated=%s",
                    preference_updated_from_tool,
                )
            else:
                try:
                    result = json.loads(text)
                except json.JSONDecodeError:
                    logger.warning("Router JSON parse failed. Raw text: %s", text)
                    result = {
                        "intent": "CHAT",
                        "request_summary": message,
                        "preference_updated": None,
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
                "preference_updated": None,
                "response": None,
                "raw_response": None,
                "latency_ms": (time.time() - t) * 1000,
            }
