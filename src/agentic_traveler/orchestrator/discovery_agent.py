from typing import Dict, Any, List, Optional
import os
from google import genai
from google.genai import types
from dotenv import load_dotenv

load_dotenv()

class DiscoveryAgent:
    """
    Agent responsible for discovering potential destinations based on user profile and constraints.
    """

    def __init__(self, api_key: Optional[str] = None, model_name: str = "gemini-3-flash-preview"):
        self.api_key = api_key or os.getenv("GOOGLE_API_KEY")
        if not self.api_key:
             # For now, we'll warn but allow initialization for testing purposes if env wrapper handles it
             pass 
        
        self.client = genai.Client(api_key=self.api_key) if self.api_key else None
        self.model_name = model_name

    def process_request(self, user_profile: Dict[str, Any], message_text: str) -> Dict[str, Any]:
        """
        Generates destination proposals.
        """
        # 1. Extract constraints from message (simplified for now, full extraction later)
        # 2. Combine with user_profile
        # 3. Call LLM to generate options
        
        if not self.client:
            return {
                "text": "I'm sorry, I can't generate travel ideas right now (Missing API Key).",
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
                "action": "DISCOVERY_RESULTS"
            }
        except Exception as e:
            return {
                "text": f"I encountered an error generating ideas: {str(e)}",
                "action": "ERROR"
            }

    def _construct_prompt(self, user_profile: Dict[str, Any], message_text: str) -> str:
        # Construct a rich prompt using the user profile
        user_name = user_profile.get("user_name", "Traveler")
        
        # Flatten profile for the prompt (simplified)
        # In a real scenario, we'd carefully select fields
        profile_summary = f"User Name: {user_name}\n"
        profile_summary += f"Preferences: {user_profile.get('preferences', {})}\n"
        
        return f"""
        Act as an expert travel agent. The user '{user_name}' is asking: "{message_text}"
        
        Based on their profile:
        {profile_summary}
        
        Suggest 3 destination candidates formatted as a list. For each, explain why it fits their profile and the current request.
        """
