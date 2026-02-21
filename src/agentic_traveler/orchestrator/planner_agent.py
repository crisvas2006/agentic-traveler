from typing import Dict, Any, Optional
import os
from google import genai
from google.genai import types
from dotenv import load_dotenv
from agentic_traveler.orchestrator.profile_utils import build_profile_summary

load_dotenv()

class PlannerAgent:
    """
    Agent responsible for creating detailed trip itineraries.
    """

    def __init__(self, api_key: Optional[str] = None, model_name: str = "gemini-3-flash-preview"):
        self.api_key = api_key or os.getenv("GOOGLE_API_KEY")
        if not self.api_key:
             pass 
        
        self.client = genai.Client(api_key=self.api_key) if self.api_key else None
        self.model_name = model_name

    def process_request(self, user_profile: Dict[str, Any], message_text: str) -> Dict[str, Any]:
        """
        Generates a trip itinerary.
        """
        if not self.client:
            return {
                "text": "I'm sorry, I can't generate an itinerary right now (Missing API Key).",
                "action": "ERROR"
            }

        prompt = self._construct_prompt(user_profile, message_text)
        
        try:
            response = self.client.models.generate_content(
                model=self.model_name,
                contents=prompt,
                config=types.GenerateContentConfig(
                    temperature=0.7,
                )
            )
            return {
                "text": response.text,
                "action": "PLANNER_RESULTS"
            }
        except Exception as e:
            return {
                "text": f"I encountered an error planning the trip: {str(e)}",
                "action": "ERROR"
            }

    def _construct_prompt(self, user_profile: Dict[str, Any], message_text: str) -> str:
        profile_summary = build_profile_summary(user_profile)

        return f"""\
You are a friendly, expert travel planner chatting with a traveler.

The traveler says: "{message_text}"

Their profile:
{profile_summary}

Create a flexible day-by-day itinerary tailored to this person's style and
energy level.  Keep it concise — use bullet points, not paragraphs.
For each day include:
- A morning, afternoon, and evening suggestion.
- One low-energy alternative per day.
- Keep the total response under 300 words.
- Tone: practical and warm, like a friend who knows the place well.
"""
