import logging
from typing import Dict, Any, Optional
from agentic_traveler.tools.firestore_user import FirestoreUserTool
from agentic_traveler.orchestrator.discovery_agent import DiscoveryAgent
from agentic_traveler.orchestrator.planner_agent import PlannerAgent
from agentic_traveler.orchestrator.companion_agent import CompanionAgent
from agentic_traveler.orchestrator.intent_classifier import IntentClassifier
from agentic_traveler.orchestrator.safety_filter import SafetyFilter
from agentic_traveler.orchestrator.chat_agent import ChatAgent

logger = logging.getLogger(__name__)


class OrchestratorAgent:
    """
    The main entry point agent that understands user intent and routes requests.
    All agent responses pass through the SafetyFilter before being returned.
    """

    def __init__(self, firestore_user_tool: Optional[FirestoreUserTool] = None):
        self.user_tool = firestore_user_tool or FirestoreUserTool()
        self.discovery_agent = DiscoveryAgent()
        self.planner_agent = PlannerAgent()
        self.companion_agent = CompanionAgent()
        self.chat_agent = ChatAgent()
        self.intent_classifier = IntentClassifier()
        self.safety_filter = SafetyFilter()

    def process_request(self, telegram_user_id: str, message_text: str) -> Dict[str, Any]:
        """
        Processes a message from a Telegram user.

        Args:
            telegram_user_id: The ID of the user sending the message.
            message_text: The content of the message.

        Returns:
            A dictionary containing the response text and any other actions.
        """
        
        # 1. Fetch User Context
        user_profile = self.user_tool.get_user_by_telegram_id(telegram_user_id)
        
        if not user_profile:
            return {
                "text": (
                    "Welcome to Agentic Traveler! I don't see a profile for you yet. "
                    "Please fill out our onboarding form to get started: https://tally.so/r/9qN6p4"
                ),
                "action": "ONBOARDING_REQUIRED"
            }

        # 2. Classify intent via LLM (with keyword fallback)
        intent = self.intent_classifier.classify(message_text)
        logger.info("Intent classified as: %s for message: %.50s…", intent, message_text)
        
        # 3. Route based on intent
        if intent == "NEW_TRIP":
            response = self._handle_new_trip(user_profile, message_text)
        elif intent == "PLANNING":
            response = self._handle_planning(user_profile, message_text)
        elif intent == "IN_TRIP":
            response = self._handle_in_trip(user_profile, message_text)
        else:
            response = self._handle_chat(user_profile, message_text)

        # 4. Apply Safety Filter to every response
        response["text"] = self.safety_filter.filter(response["text"])
        return response

    def _handle_new_trip(self, user_profile: Dict[str, Any], text: str) -> Dict[str, Any]:
        return self.discovery_agent.process_request(user_profile, text)

    def _handle_planning(self, user_profile: Dict[str, Any], text: str) -> Dict[str, Any]:
        return self.planner_agent.process_request(user_profile, text)

    def _handle_in_trip(self, user_profile: Dict[str, Any], text: str) -> Dict[str, Any]:
        return self.companion_agent.process_request(user_profile, text)

    def _handle_chat(self, user_profile: Dict[str, Any], text: str) -> Dict[str, Any]:
        return self.chat_agent.process_request(user_profile, text)
