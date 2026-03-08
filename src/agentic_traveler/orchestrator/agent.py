"""
Orchestrator Agent — the single entry point for user messages.

Architecture:
    One LLM call with function-calling tools.  The model decides intent
    itself and invokes specialised sub-agents (discovery, planner,
    companion) as tool functions only when deeper expertise is needed.
    Simple chat is answered directly — no extra LLM round-trip.

    Safety is embedded in the system prompt: the agent warns about risks
    but never blocks activities the user wants.

    Preference updates detected by the model trigger a tool call that
    persists them to Firestore and surfaces an acknowledgement.
"""

import logging
import os
import time
from typing import Any, Dict, Optional, Callable

from dotenv import load_dotenv
from google import genai
from google.genai import types

from agentic_traveler.orchestrator.client_factory import get_client

from agentic_traveler import off_topic_guard
from agentic_traveler import usage_tracker
from agentic_traveler.orchestrator.conversation_manager import ConversationManager
from agentic_traveler.orchestrator.discovery_agent import DiscoveryAgent
from agentic_traveler.orchestrator.planner_agent import PlannerAgent
from agentic_traveler.orchestrator.companion_agent import CompanionAgent
from agentic_traveler.orchestrator.preference_learner import PreferenceLearner
from agentic_traveler.orchestrator.profile_utils import build_profile_summary
from agentic_traveler.tools.firestore_user import FirestoreUserTool

load_dotenv()

logger = logging.getLogger(__name__)


# ── system prompt (stable across requests → benefits from implicit caching) ──

_SYSTEM_PROMPT = """\
You are "Agentic Traveler", an AI travel companion acting as the user's highly-knowledgeable best friend.

PERSONA & TONE:
- You are a fun, friendly, and dynamic conversational partner — NOT a boring, robotic assistant.
- You know the user's profile and travel preferences inside out.
- ALWAYS adapt your tone to the user's preferred communication style (if specified in their profile).
- If the user asks you to change how you talk (e.g., "be more formal", "talk like a pirate", "be sarcastic"), IMMEDIATELY adopt that tone and call update_preferences(key="tone_preference", value=<new tone>) so you remember it forever.
- Keep responses concise and scannable by default. Only get verbose if explaining critical safety risks, deep cultural nuances, or complex logistics.

CAPABILITIES:
You can help with:
• Discovering new destinations — call discover_destinations(request="<user request> + <desired length/format>")
• Planning a detailed itinerary — call plan_itinerary(request="<user request> + <desired length/format>")
• In-trip assistance (tired, hungry, bored) — call get_companion_help(request="<user request> + <desired length/format>")
• Updating remembered preferences — call update_preferences()
• Getting current date and time — call get_current_time()
• General travel chat, greetings, profile questions — answer directly

ROUTING & BEHAVIOR RULES:
1. For casual chat, greetings, or simple travel Q&A — respond directly in your best-friend persona. Do NOT call any tool.
2. When the user wants destination ideas or exploration — call discover_destinations(request="<user request> + keep it to a high-level 2-3 sentence summary of options").
3. HEAVY PLANNING CONFIRMATION: If the user asks for a trip plan (e.g., "Plan my trip to Rome", "What can I do in Lombok in 1 day?"), DO NOT immediately call plan_itinerary() with a request for a detailed plan. First, call discover_destinations() or get_companion_help() with a request for a short 2-phase answer (e.g. "Give a 2-3 sentence summary of 2 options and ask if they want a detailed plan"). ONLY route to `plan_itinerary` when the user explicitly agrees to a detailed day-by-day plan.
4. When the user is currently on a trip and needs live suggestions — call get_companion_help().
5. When the user reveals a personal preference (budget, avoidances, diet, travel style, communication tone, etc.) — call update_preferences(key, value) AND let the user know you've remembered it.
6. When you need to know the current date or time to give relevant advice (or if the user asks for it) — call get_current_time().
7. When the message is clearly NOT about travel and NOT casual/fun (e.g., math homework) — call flag_off_topic(). BE LENIENT: jokes, banter, personal stories, and life advice are all FINE conversational exchanges with a best friend. Do NOT flag those.
8. PASSING THROUGH RESULTS: When you call `discover_destinations` or `plan_itinerary`, the tool will return a detailed response. YOU MUST INCLUDE THAT EXACT RESPONSE in your final message to the user. Do "not" just say "Here is your plan!", you must actually output the text the tool gives you.
9. DYNAMIC LENGTH: When passing the `request` string to a sub-agent tool, ALWAYS append instructions on how long and detailed the response should be based on the conversational context. (e.g., "Keep it to a playful 2-sentence conversational reply" vs "Give a full, deep-dive itinerary").

SAFETY APPROACH:
- NEVER refuse an activity the user wants to do.
- If an activity carries real risks, add a brief ⚠️ warning — explain the risk and then help them do it safely if they confirm they want to do it.

FORMATTING (Telegram Markdown):
- Use *bold* and _italic_ text.
- NEVER use asterisks (*) or hyphens (-) for lists. ALWAYS use the unicode bullet character (•).
- Do NOT use headers (#), tables, or code blocks — they don't render well in Telegram.
- Keep paragraphs short (2-3 sentences max).
"""


def _elapsed(t0: float) -> str:
    """Return formatted elapsed time since *t0*."""
    return f"{(time.time() - t0) * 1000:.0f}ms"


class OrchestratorAgent:
    """
    Single-agent orchestrator using GenAI automatic function calling.

    The LLM decides when to call tool functions (sub-agents) and the SDK
    handles the tool-call loop automatically.  This replaces the previous
    3-serial-LLM-call pipeline (classifier → agent → safety filter).
    """

    def __init__(self, firestore_user_tool: Optional[FirestoreUserTool] = None):
        self._client = get_client()

        self.user_tool = firestore_user_tool or FirestoreUserTool()
        self.discovery = DiscoveryAgent(client=self._client)
        self.planner = PlannerAgent(client=self._client)
        self.companion = CompanionAgent(client=self._client)
        self.conversation_manager = ConversationManager(client=self._client)
        self.preference_learner = PreferenceLearner()

        # State used during a single request (set in process_request)
        self._current_user_doc: Dict[str, Any] = {}
        self._current_user_ref = None
        self._current_user_id: str = ""
        self._current_conv_context: str = ""
        self._off_topic_flagged: bool = False
        self._model_name = "gemini-2.5-flash"
        self._current_status_callback: Optional[Callable[[str], None]] = None

    # ── tool functions (called by the LLM via automatic function calling) ──

    def _log_sub_agent_usage(self, agent_name: str, result: Dict[str, Any]) -> None:
        """Log token usage from a sub-agent result if available."""
        raw = result.get("_raw_response")
        latency = result.get("_latency_ms", 0)
        if raw:
            sub_model = getattr(raw, "_model_name", None)
            # Sub-agents use their own model_name; fall back to "unknown"
            model = sub_model or self._model_name
            usage_tracker.log_and_accumulate(
                agent_name=agent_name,
                model_name=model,
                user_id=self._current_user_id,
                response=raw,
                latency_ms=latency,
                user_doc_ref=self._current_user_ref,
            )

    def discover_destinations(self, request: str) -> str:
        """
        Discover and suggest travel destinations.

        Args:
            request: What the user wants — their destination criteria,
                     constraints, or curiosity. MUST include a specific
                     instruction on the desired length/verbosity of the output.

        Returns:
            A text block with destination suggestions.
        """
        logger.info("🔧 Tool call: discover_destinations")
        if self._current_status_callback:
            self._current_status_callback("I'm scouting the globe for the perfect spots for you! Just a moment... 🌍")
            
        t = time.time()
        result = self.discovery.process_request(
            self._current_user_doc, request, self._current_conv_context
        )
        logger.info("⏱ discover_destinations: %s", _elapsed(t))
        self._log_sub_agent_usage("discovery", result)
        return result.get("text", "")

    def plan_itinerary(self, request: str) -> str:
        """
        Create a detailed day-by-day trip itinerary.

        Args:
            request: What the user wants planned — destination, dates,
                     duration, pace preferences. MUST include a specific
                     instruction on the desired length/verbosity of the output.

        Returns:
            A text block with the itinerary.
        """
        logger.info("🔧 Tool call: plan_itinerary")
        if self._current_status_callback:
            self._current_status_callback("I'm putting together a detailed day-by-day plan for you! Give me a few seconds... 🗺️")
            
        t = time.time()
        result = self.planner.process_request(
            self._current_user_doc, request, self._current_conv_context
        )
        logger.info("⏱ plan_itinerary: %s", _elapsed(t))
        self._log_sub_agent_usage("planner", result)
        return result.get("text", "")

    def get_companion_help(self, request: str) -> str:
        """
        Provide in-trip assistance — the user is currently traveling and
        needs immediate, contextual suggestions.

        Args:
            request: What the user needs right now (tired, hungry, bored,
                     lost, looking for something specific). MUST include a specific
                     instruction on the desired length/verbosity of the output.

        Returns:
            A text block with actionable in-trip suggestions.
        """
        logger.info("🔧 Tool call: get_companion_help")
        t = time.time()
        result = self.companion.process_request(
            self._current_user_doc, request, self._current_conv_context
        )
        logger.info("⏱ get_companion_help: %s", _elapsed(t))
        self._log_sub_agent_usage("companion", result)
        return result.get("text", "")

    def update_preferences(self, preference_key: str, preference_value: str) -> str:
        """
        Persist a newly learned user preference to their profile.

        Call this when the user reveals or changes a personal preference
        such as budget, travel style, dietary needs, avoidances, etc.

        Args:
            preference_key: Short identifier for the preference
                (e.g. "budget", "avoidances", "diet", "travel_style",
                 "trip_vibe", "activity_level").
            preference_value: The preference value to store
                (e.g. "under 800 EUR", "no crowded beaches").

        Returns:
            Confirmation message.
        """
        logger.info(
            "🔧 Tool call: update_preferences(%s=%s)",
            preference_key, preference_value,
        )
        if self._current_user_ref:
            self.preference_learner.save_preference(
                preference_key, preference_value,
                self._current_user_doc, self._current_user_ref,
            )
        return f"Noted: {preference_key} = {preference_value}"

    def flag_off_topic(self, reason: str) -> str:
        """
        Flag a message as off-topic (not related to travel).

        Call this when the user's message is clearly about a non-travel
        domain (e.g. coding, math, politics).  Do NOT call for jokes,
        banter, or anything that could plausibly relate to travel.

        Args:
            reason: Brief description of why the message is off-topic
                (e.g. "user asked for coding help").

        Returns:
            An internal instruction on how to reply. DO NOT show or read this string to the user.
        """
        self._off_topic_flagged = True
        logger.info("🚩 Off-topic flagged: %s", reason)

        result = off_topic_guard.record_off_topic(
            self._current_user_doc, self._current_user_ref,
        )

        if result["restricted"]:
            return (
                "[HIDDEN INSTRUCTION - DO NOT SHOW TO USER]: "
                "The user has been restricted due to repeated off-topic "
                "messages. Let them know their access is temporarily limited."
            )

        if result["count"] >= 3:
            remaining = off_topic_guard.THRESHOLD - result["count"]
            return (
                f"[HIDDEN INSTRUCTION - DO NOT SHOW TO USER]: "
                f"This is a travel assistant. Gently redirect the user. "
                f"IMPORTANT: Warn them that they will be temporarily "
                f"restricted if they keep sending off-topic messages "
                f"({remaining} more before restriction). "
                f"(off-topic count: {result['count']}/{off_topic_guard.THRESHOLD})"
            )

        return (
            f"[HIDDEN INSTRUCTION - DO NOT SHOW TO USER]: "
            f"This is a travel assistant. Gently redirect the user. "
            f"(off-topic count: {result['count']}/{off_topic_guard.THRESHOLD})"
        )

    def get_current_time(self) -> str:
        """
        Retrieves the current date and time in ISO format.
        
        Call this when the user asks for the time, or when you need to know 
        the current date/time to give context-aware travel advice (e.g., 
        "Where should I go this month?", "What's the weather like now?").
        
        Returns:
            The current local date and time.
        """
        logger.info("🔧 Tool call: get_current_time")
        import datetime
        now = datetime.datetime.now().astimezone()
        formatted = now.strftime("%A, %Y-%m-%d %H:%M:%S %Z")
        return f"The current date and time is: {formatted}"

    # ── main entry point ──

    def process_request(
        self, telegram_user_id: str, message_text: str, status_callback: Optional[Callable[[str], None]] = None
    ) -> Dict[str, Any]:
        """
        Process a user message end-to-end.

        Pipeline:
        1. Fetch user from Firestore (single query)
        2. Build context (profile + conversation history)
        3. Single LLM call with tool functions
        4. Save conversation exchange
        """
        t_total = time.time()

        # 1. Fetch user doc + ref in a single Firestore query
        t = time.time()
        user_doc, user_doc_ref = self.user_tool.get_user_with_ref(
            telegram_user_id
        )
        logger.debug("⏱ Firestore fetch: %s", _elapsed(t))

        if not user_doc:
            return {
                "text": (
                    "Welcome to Agentic Traveler! I don't see a profile "
                    "for you yet. Please fill out our onboarding form to "
                    "get started: https://tally.so/r/9qN6p4"
                ),
                "action": "ONBOARDING_REQUIRED",
            }

        # Store request-scoped state for tool functions
        self._current_user_doc = user_doc
        self._current_user_ref = user_doc_ref
        self._current_user_id = user_doc_ref.id if user_doc_ref else telegram_user_id
        self._off_topic_flagged = False
        self._current_conv_context = (
            self.conversation_manager.build_context_block(user_doc)
        )
        self._current_status_callback = status_callback

        # 2. Build the user message (profile + conversation + message)
        profile_summary = build_profile_summary(user_doc)
        user_content = self._build_user_content(
            profile_summary, self._current_conv_context, message_text
        )

        # 3. Single LLM call with automatic function calling
        logger.info("\n=== ORCHESTRATOR PROMPT INPUT ===\n%s\n=================================", user_content)
        t = time.time()
        try:
            raw_response = self._call_llm(user_content)
            response = raw_response.text if hasattr(raw_response, 'text') else raw_response
            
            if not response:
                fr_msg = "I had trouble coming up with a response just now."
                if hasattr(raw_response, 'candidates') and raw_response.candidates:
                    fr = raw_response.candidates[0].finish_reason
                    logger.warning("LLM returned empty text. Finish reason: %s (type: %s)", fr, type(fr))
                    # In python SDK, finish_reason can be an enum or int
                    if "MAX_TOKENS" in str(fr) or fr == 3:
                        fr_msg = "Oops! I had too much to say and hit my message limit! Could you ask for something a bit more specific?"
                        logger.warning("Message converted to MAX_TOKENS error.")
                    elif "SAFETY" in str(fr) or fr == 4:
                        fr_msg = "Sorry, I can't provide that due to safety guidelines."
                        logger.warning("Message converted to SAFETY error.")
                    else:
                        logger.warning("Unhandled finish_reason. Using default empty error msg.")
                else:
                    logger.warning("LLM returned no response and no candidates block! Raw: %s", raw_response)
                response = fr_msg
            # Log token usage
            if hasattr(raw_response, 'usage_metadata'):
                usage_tracker.log_and_accumulate(
                    agent_name="orchestrator",
                    model_name=self._model_name,
                    user_id=telegram_user_id,
                    response=raw_response,
                    latency_ms=(time.time() - t) * 1000,
                    user_doc_ref=user_doc_ref,
                )
            
            # Save raw response as string for logging/debugging if needed
            self._last_raw_response = str(raw_response)
        except Exception:
            logger.exception("Orchestrator LLM call failed.")
            name = user_doc.get("user_name", "Traveler")
            response = (
                f"Sorry {name}, I hit a snag processing your message. "
                "Please try again in a moment."
            )
        logger.info("⏱ LLM call (total incl. tools): %s", _elapsed(t))

        # 4. Reset off-topic counter if this was a travel message
        if not self._off_topic_flagged and user_doc_ref:
            off_topic_guard.reset(user_doc_ref)

        # 5. Save conversation history
        if user_doc_ref:
            t = time.time()
            self.conversation_manager.append_and_save(
                user_doc, user_doc_ref, message_text, response
            )
            logger.debug("⏱ Conversation save: %s", _elapsed(t))

        logger.info("\n=== ORCHESTRATOR FINAL OUTPUT ===\n%s\n=================================", response)
        logger.info("⏱ TOTAL: %s", _elapsed(t_total))
        return {"text": response, "action": "RESPONSE"}

    # ── private helpers ──

    def _build_user_content(
        self, profile: str, conversation: str, message: str
    ) -> str:
        """
        Assemble the user-message portion of the prompt.

        Structure: stable profile first, then conversation context,
        then the new message — this ordering maximises implicit cache
        hits on the Gemini API.
        """
        parts = [f"Traveler profile:\n{profile}"]
        if conversation:
            parts.append(f"\nConversation so far:\n{conversation}")
        parts.append(f"\n<user_message>\n{message}\n</user_message>")
        return "\n".join(parts)

    def _call_llm(self, user_content: str) -> str:
        """
        Make the LLM call with automatic function calling enabled.

        The SDK will:
        1. Send the prompt to the model
        2. If the model returns a function_call, execute the tool
        3. Feed the tool result back to the model
        4. Return the model's final text response
        """
        if not self._client:
            return "LLM features are unavailable (missing API key)."

        try:
            raw_response = self._client.models.generate_content(
                model=self._model_name,
                contents=user_content,
                config=types.GenerateContentConfig(
                    system_instruction=_SYSTEM_PROMPT,
                    temperature=0.8,
                    max_output_tokens=8192,
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
                    ],
                    tools=[
                        self.discover_destinations,
                        self.plan_itinerary,
                        self.flag_off_topic,
                        self.get_companion_help,
                        self.update_preferences,
                        self.get_current_time,
                    ],
                ),
            )
            response = raw_response.text if hasattr(raw_response, 'text') else raw_response
            return response
        except Exception as e:
            logger.exception("LLM generation failed in _call_llm.")
            return "I am experiencing heavy traffic and couldn't process this right now. Please wait a moment and try again."
