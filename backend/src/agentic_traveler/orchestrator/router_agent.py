"""
Router Agent — lightweight intent classifier and action planner.

Classifies user messages into CHAT | TRIP | PLAN | OFF_TOPIC and decides which
lightweight side-effects to run (preference save, app feedback, credit answer).

Design: structured-output classification, deterministic execution.
    The model returns a SINGLE JSON object describing the message — the intent
    plus any actions to take (new_preference, feedback, response). Plain Python
    then performs the side-effects. We deliberately do NOT use Gemini Automatic
    Function Calling (AFC) here: combining AFC with response_mime_type="application/json"
    on flash-lite is unstable — the model spams function calls until the remote-call
    limit and never emits the JSON. A single structured response is reliable, cheaper
    (one model turn), and makes each side-effect fire at most once by construction.

OFF_TOPIC messages: the router generates a natural, warm redirection response in
the "response" field, while the orchestration layer silently increments the
off-topic counter.
"""

import json
import logging
import time
from typing import Any, Dict, Optional

from google import genai
from google.genai import types

from agentic_traveler.orchestrator.client_factory import get_client, gemini_generate
from agentic_traveler.core.observability import traceable
from agentic_traveler.orchestrator.profile_agent import ProfileAgent
from agentic_traveler.tools.feedback_tool import FeedbackTool
from agentic_traveler.economy import credit_manager

logger = logging.getLogger(__name__)

_MODEL = "gemini-3.1-flash-lite"

_VALID_INTENTS = {"CHAT", "TRIP", "PLAN", "OFF_TOPIC"}
_VALID_FEEDBACK_CATEGORIES = {"positive", "negative", "suggestion"}

_SYSTEM_PROMPT = """\
You are the intent router for Agentic Traveler, a travel companion chatbot.

Your job: read the LATEST USER MESSAGE and return ONE JSON object describing it.
You do NOT call any functions — you only fill in the JSON fields below.

STEP 1 — Pick the intent:

• CHAT — Greetings, thanks, jokes, banter, personal stories, emotional support, life
  advice, opinions, or any conversational message not asking for travel help.
  Examples: "hey!", "thanks!", "how are you?", "tell me a joke", "I'm feeling stressed"

• TRIP — Travel questions, destination research, in-trip help, weather, visa questions,
  or travel advice. Travel questions are TRIP regardless of the language they are
  written in.
  Examples: "what should I do in Bali?", "is Lombok worth it?", "best time to visit Japan?",
  "I'm tired and it's raining", "Qu'est-ce que je peux faire à Paris en décembre?"

• PLAN — An explicit request for a structured day-by-day itinerary or trip schedule.
  Examples: "plan my 5-day trip to Rome", "make me an itinerary for Lombok", "help me plan day by day"

• OFF_TOPIC — Clearly unrelated to travel AND not casual conversation (math, coding,
  politics…). Be lenient: jokes, banter, and life advice are CHAT, not OFF_TOPIC.

STEP 2 — Fill "new_preference" (string) ONLY IF the LATEST USER MESSAGE is a first-person
preference DECLARATION. Otherwise set it to null.
  Set it to the verbatim preference text when the message contains a trigger phrase:
    "I always [X]" · "I prefer [X]" · "I never [X]" · "I only [X]"
    "I'm [dietary/lifestyle label]" · "I avoid [X]" · "never suggest [X] to me"
  Set it to null when ANY of these is true:
    - The message is a question (starts with What/How/Where/When/Why/Which/Is/Are/Can/
      Could/Would/Do/Does/Did/Will, or ends with "?"). Questions are NEVER declarations.
    - The message is a greeting, thanks, banter, or emotional venting.
    - The preference already appears in Known Preferences or Conversation History.
  CRITICAL: only ever copy text from the LATEST USER MESSAGE. Never reconstruct a
  preference from Known Preferences or Conversation History — those are READ-ONLY.

STEP 3 — Fill "feedback_category" + "feedback_text" ONLY IF the LATEST USER MESSAGE
directly addresses THIS app or bot ("you", "this app", "your responses") and evaluates
it or requests a feature. Otherwise set both to null.
  feedback_category ∈ {"positive", "negative", "suggestion"}
  feedback_text = the verbatim feedback from the LATEST USER MESSAGE.
  Set both to null for real-world complaints (a hotel, the weather, planning fatigue)
  and for off-topic requests ("Can you help me debug my code?") — those are not feedback.

STEP 4 — Fill "response" (string) ONLY in these two cases, else null:
    - OFF_TOPIC: a short, warm redirection back to travel, in the user's language, warning the user that multiple off topic messages will result in suspending the capability to use the chat feature.
    - The user asks about their credit balance: answer using the Credit Balance shown
      in the context below (e.g. "You currently have 200 credits left.").
  For every other message, set "response" to null.

A single message can legitimately set several fields at once (e.g. a new preference AND
positive feedback AND a TRIP intent). Each action field is filled at most once.

EXAMPLES (message → the non-null fields you should set):
  "hey thanks!" → intent=CHAT
  "I'm so tired of planning" → intent=CHAT (venting, not a preference)
  "What's the best neighbourhood to stay in when visiting Lisbon?" → intent=TRIP (question)
  "Qu'est-ce que je peux faire à Paris?" → intent=TRIP (travel question, any language)
  "Can you help me debug this Python stack trace?" → intent=OFF_TOPIC, response=<redirect>
  "What did I tell you about my diet?" → intent=CHAT (recall question, new_preference=null)
  "What are my travel preferences?" → intent=CHAT (lookup question, new_preference=null)
  "How many credits do I have left?" → intent=CHAT, response=<balance from context>
  "This app is amazing!" → intent=CHAT, feedback_category=positive, feedback_text="This app is amazing!"
  "You should add a dark mode" → intent=CHAT, feedback_category=suggestion, feedback_text="You should add a dark mode"
  "The hotel was terrible, I'm so annoyed" → intent=CHAT (real-world complaint, no feedback)
  "I always book Ibis Hotels" → intent=CHAT, new_preference="I always book Ibis Hotels"
  "I'm vegetarian, plan my Rome trip" → intent=PLAN, new_preference="I'm vegetarian"
  "I'm vegan and this app is amazing!" → intent=CHAT, new_preference="I'm vegan",
        feedback_category=positive, feedback_text="this app is amazing!"

Return ONLY the JSON object, nothing else.
"""


def _response_schema() -> types.Schema:
    """Structured-output schema. Enforces field presence; nullable for optional actions."""
    return types.Schema(
        type=types.Type.OBJECT,
        required=["intent", "request_summary"],
        properties={
            "intent": types.Schema(
                type=types.Type.STRING,
                enum=["CHAT", "TRIP", "PLAN", "OFF_TOPIC"],
            ),
            "request_summary": types.Schema(type=types.Type.STRING),
            "new_preference": types.Schema(type=types.Type.STRING, nullable=True),
            "feedback_category": types.Schema(type=types.Type.STRING, nullable=True),
            "feedback_text": types.Schema(type=types.Type.STRING, nullable=True),
            "response": types.Schema(type=types.Type.STRING, nullable=True),
        },
    )


def _clean(value: Any) -> Optional[str]:
    """Normalise a model-emitted optional string: treat null/empty/'null' as None."""
    if value is None:
        return None
    text = str(value).strip()
    if not text or text.lower() in {"null", "none"}:
        return None
    return text


class RouterAgent:
    """
    Thin intent router. Classifies messages and runs lightweight side-effects.

    Stateless service — initialize once, reuse across parallel requests.
    """

    def __init__(self, client: Optional[genai.Client] = None):
        self._client = client or get_client()
        # Share the single genai.Client across sub-agents (task_16 invariant).
        # ProfileAgent otherwise calls get_client() again and spins up a second
        # Vertex client + connection pool.
        self._profile_agent = ProfileAgent(client=self._client)
        self._feedback_tool = FeedbackTool()

    @traceable(name="router.classify")
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
        Classify user intent and run any lightweight side-effects the message warrants.

        Returns a dict with keys:
            intent: str — CHAT | TRIP | PLAN | OFF_TOPIC
            request_summary: str
            preference_raw: str | None  — the preference that was saved this turn, if any
            response: str | None        — only set for OFF_TOPIC or a credit-balance answer
            raw_response: the raw genai response (for token logging)
            latency_ms: float
        """
        _ = telegram_user_id  # part of the public signature; not needed here

        from agentic_traveler.orchestrator.profile_utils import build_profile_summary
        known_prefs = build_profile_summary(user_doc, include_scores=False, include_summary=True)
        if user_doc.get("language"):
            known_prefs += f"\nLanguage: {user_doc.get('language')}"
        if not known_prefs:
            known_prefs = "None"

        balance = credit_manager.get_balance(user_doc)

        user_prompt = f"""\
Current Time: {current_time}
User Name: {user_name}
Credit Balance: {balance} credits
Known Preferences: {known_prefs}

Conversation History:
{conversation_context}

LATEST USER MESSAGE:
{message}
"""

        t = time.time()
        try:
            raw = gemini_generate(
                self._client,
                model=_MODEL,
                contents=user_prompt,
                config=types.GenerateContentConfig(
                    system_instruction=_SYSTEM_PROMPT,
                    max_output_tokens=400,
                    response_mime_type="application/json",
                    response_schema=_response_schema(),
                    # The router uses structured output, not tools. Disable AFC
                    # explicitly so the SDK never enables it by default (keeps
                    # logs clean and guarantees a single, loop-free model turn).
                    automatic_function_calling=types.AutomaticFunctionCallingConfig(
                        disable=True,
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
                ),
            )
            latency_ms = (time.time() - t) * 1000

            parsed = self._parse(raw.text, message)

            # ── deterministic side-effects ───────────────────────────────────
            # Each fires at most once because each is a single field, not a
            # repeatable function call.
            new_preference = parsed["new_preference"]
            if new_preference and user_id:
                logger.info("🔧 Router action: save_stated_preference(%s)", new_preference)
                self._profile_agent.save_preference(new_preference, user_doc, user_id)

            if parsed["feedback_category"] and user_id:
                logger.info(
                    "🔧 Router action: save_app_feedback(category=%s)",
                    parsed["feedback_category"],
                )
                self._feedback_tool.record(
                    user_id=user_id,
                    text=parsed["feedback_text"] or message,
                    category=parsed["feedback_category"],
                    user_doc=user_doc,
                    _sync=False,
                )

            result = {
                "intent": parsed["intent"],
                "request_summary": parsed["request_summary"],
                "preference_raw": new_preference,
                "response": parsed["response"],
                "raw_response": raw,
                "latency_ms": latency_ms,
            }
            logger.info(
                "Router classified '%s' → %s (%.0fms)",
                message[:60], result["intent"], latency_ms,
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

    # ------------------------------------------------------------------
    # Parsing
    # ------------------------------------------------------------------

    @staticmethod
    def _parse(text: Optional[str], message: str) -> Dict[str, Any]:
        """
        Parse and sanitise the model's JSON. Always returns a complete dict with
        normalised values, falling back to a safe CHAT classification on any problem.
        """
        fallback = {
            "intent": "CHAT",
            "request_summary": message,
            "new_preference": None,
            "feedback_category": None,
            "feedback_text": None,
            "response": None,
        }

        if not text:
            logger.warning("Router returned empty text — defaulting to CHAT.")
            return fallback

        try:
            data = json.loads(text)
        except json.JSONDecodeError:
            logger.warning("Router JSON parse failed. Raw text: %s", text[:200])
            return fallback

        intent = str(data.get("intent", "")).strip().upper()
        if intent not in _VALID_INTENTS:
            logger.warning("Router emitted invalid intent %r — defaulting to CHAT.", intent)
            intent = "CHAT"

        category = _clean(data.get("feedback_category"))
        if category is not None:
            category = category.lower()
            if category not in _VALID_FEEDBACK_CATEGORIES:
                logger.warning("Router emitted invalid feedback_category %r — ignoring.", category)
                category = None

        return {
            "intent": intent,
            "request_summary": _clean(data.get("request_summary")) or message,
            "new_preference": _clean(data.get("new_preference")),
            "feedback_category": category,
            "feedback_text": _clean(data.get("feedback_text")),
            "response": _clean(data.get("response")),
        }
