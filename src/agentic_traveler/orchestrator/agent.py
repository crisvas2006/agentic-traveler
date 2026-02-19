from typing import Dict, Any, Optional
from agentic_traveler.tools.firestore_user import FirestoreUserTool
from agentic_traveler.orchestrator.discovery_agent import DiscoveryAgent
from agentic_traveler.orchestrator.planner_agent import PlannerAgent

class OrchestratorAgent:
    """
    The main entry point agent that understands user intent and routes requests.
    """

    def __init__(self, firestore_user_tool: Optional[FirestoreUserTool] = None):
        self.user_tool = firestore_user_tool or FirestoreUserTool()
        self.discovery_agent = DiscoveryAgent()
        self.planner_agent = PlannerAgent()

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
            # New user flow
            return {
                "text": (
                    "Welcome to Agentic Traveler! I don't see a profile for you yet. "
                    "Please fill out our onboarding form to get started: https://tally.so/r/9qN6p4"
                ),
                "action": "ONBOARDING_REQUIRED"
            }

        # 2. Determine Intent (Mocked for now, will use LLM later)
        intent = self._determine_intent(message_text)
        
        # 3. Route based on intent
        if intent == "NEW_TRIP":
            return self._handle_new_trip(user_profile, message_text)
        elif intent == "PLANNING":
            return self._handle_planning(user_profile, message_text)
        elif intent == "IN_TRIP":
            return self._handle_in_trip(user_profile, message_text)
        else:
            return self._handle_chat(user_profile, message_text)

    def _determine_intent(self, text: str) -> str:
        """
        Simple heuristic intent classification.
        """
        text_lower = text.lower()
        if any(word in text_lower for word in ["itinerary", "schedule", "detailed plan"]):
             return "PLANNING"
        if any(word in text_lower for word in ["plan", "trip", "go to", "visit", "vacation"]):
            return "NEW_TRIP"
        if any(word in text_lower for word in ["here", "now", "tired", "hungry", "bored"]):
            return "IN_TRIP"
        return "CHAT"

    def _handle_new_trip(self, user_profile: Dict[str, Any], text: str) -> Dict[str, Any]:
        # Delegate to Discovery Agent
        return self.discovery_agent.process_request(user_profile, text)

    def _handle_planning(self, user_profile: Dict[str, Any], text: str) -> Dict[str, Any]:
        # Delegate to Planner Agent
        return self.planner_agent.process_request(user_profile, text)

    def _handle_in_trip(self, user_profile: Dict[str, Any], text: str) -> Dict[str, Any]:
        # Mock Planner/Companion Agent call
        return {
            "text": f"I'm here to help with your current trip. (Mock: Companion Agent triggered for '{text}')",
            "action": "COMPANION_TRIGGERED"
        }

    def _handle_chat(self, user_profile: Dict[str, Any], text: str) -> Dict[str, Any]:
        # General chat
        name = user_profile.get("user_name", "Traveler")
        return {
            "text": f"Hello {name}! How can I help you with your travels today?",
            "action": "CHAT_REPLY"
        }
