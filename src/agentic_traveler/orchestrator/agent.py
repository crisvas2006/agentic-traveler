import logging
import os
import time
from typing import Dict, Any, Optional

from dotenv import load_dotenv
from google import genai

from agentic_traveler.tools.firestore_user import FirestoreUserTool
from agentic_traveler.orchestrator.discovery_agent import DiscoveryAgent
from agentic_traveler.orchestrator.planner_agent import PlannerAgent
from agentic_traveler.orchestrator.companion_agent import CompanionAgent
from agentic_traveler.orchestrator.chat_agent import ChatAgent
from agentic_traveler.orchestrator.intent_classifier import IntentClassifier
from agentic_traveler.orchestrator.safety_filter import SafetyFilter
from agentic_traveler.orchestrator.conversation_manager import ConversationManager
from agentic_traveler.orchestrator.preference_learner import PreferenceLearner

load_dotenv()

logger = logging.getLogger(__name__)


def _elapsed(t0: float) -> str:
    """Return formatted elapsed time since *t0*."""
    return f"{(time.time() - t0) * 1000:.0f}ms"


class OrchestratorAgent:
    """
    The main entry point agent that understands user intent and routes requests.

    Creates a **single** ``genai.Client`` and shares it with every sub-agent
    to avoid redundant connection setup on each message.

    Pipeline:
    1. Load user document from Firestore (single query for doc + ref)
    2. Classify intent (+ preference flag)
    3. Build conversation context
    4. Route to the appropriate agent
    5. If preference flag — extract and persist new preferences
    6. Save conversation exchange
    7. Apply safety filter
    """

    def __init__(self, firestore_user_tool: Optional[FirestoreUserTool] = None):
        # --- shared LLM client (one connection for all agents) ---
        api_key = os.getenv("GOOGLE_API_KEY")
        self._genai_client = genai.Client(api_key=api_key) if api_key else None
        if not self._genai_client:
            logger.warning("No GOOGLE_API_KEY — LLM features will be unavailable.")

        self.user_tool = firestore_user_tool or FirestoreUserTool()
        self.discovery_agent = DiscoveryAgent(client=self._genai_client)
        self.planner_agent = PlannerAgent(client=self._genai_client)
        self.companion_agent = CompanionAgent(client=self._genai_client)
        self.chat_agent = ChatAgent(client=self._genai_client)
        self.intent_classifier = IntentClassifier(client=self._genai_client)
        self.safety_filter = SafetyFilter(client=self._genai_client)
        self.conversation_manager = ConversationManager(client=self._genai_client)
        self.preference_learner = PreferenceLearner(client=self._genai_client)

    def process_request(self, telegram_user_id: str, message_text: str) -> Dict[str, Any]:
        """
        Processes a message from a Telegram user.

        Each step is timed (visible in verbose/DEBUG mode) so we can
        identify exactly where latency comes from.
        """
        t_total = time.time()

        # 1. Fetch User Context — single Firestore query for doc + ref
        t = time.time()
        user_doc, user_doc_ref = self.user_tool.get_user_with_ref(telegram_user_id)
        logger.debug("⏱ Firestore fetch: %s", _elapsed(t))

        if not user_doc:
            return {
                "text": (
                    "Welcome to Agentic Traveler! I don't see a profile for you yet. "
                    "Please fill out our onboarding form to get started: https://tally.so/r/9qN6p4"
                ),
                "action": "ONBOARDING_REQUIRED"
            }

        # 2. Classify intent (+ preference flag)
        t = time.time()
        intent, has_pref = self.intent_classifier.classify(message_text)
        logger.info(
            "⏱ Intent classification: %s — %s | has_pref=%s",
            _elapsed(t), intent, has_pref,
        )

        # 3. Build conversation context (local, no network)
        conv_context = self.conversation_manager.build_context_block(user_doc)

        # 4. Route based on intent
        t = time.time()
        if intent == "NEW_TRIP":
            response = self.discovery_agent.process_request(user_doc, message_text, conv_context)
        elif intent == "PLANNING":
            response = self.planner_agent.process_request(user_doc, message_text, conv_context)
        elif intent == "IN_TRIP":
            response = self.companion_agent.process_request(user_doc, message_text, conv_context)
        else:
            response = self.chat_agent.process_request(user_doc, message_text, conv_context)
        logger.info("⏱ Agent response (%s): %s", intent, _elapsed(t))

        # 5. Extract & persist preferences if flagged
        if has_pref and user_doc_ref:
            t = time.time()
            extracted = self.preference_learner.extract_and_save(
                message_text, user_doc, user_doc_ref
            )
            logger.info("⏱ Preference extraction: %s — %s", _elapsed(t), list(extracted.keys()))

        # 6. Save conversation exchange
        if user_doc_ref:
            t = time.time()
            self.conversation_manager.append_and_save(
                user_doc, user_doc_ref, message_text, response.get("text", "")
            )
            logger.debug("⏱ Conversation save: %s", _elapsed(t))

        # 7. Apply Safety Filter
        t = time.time()
        response["text"] = self.safety_filter.filter(response["text"])
        logger.info("⏱ Safety filter: %s", _elapsed(t))

        logger.info("⏱ TOTAL: %s — action=%s", _elapsed(t_total), response.get("action"))
        return response
