import os
from typing import Dict, Optional

from google import genai
from google.genai import types
from dotenv import load_dotenv

load_dotenv()

class TravelAgent:
    """
    A simple AI agent that generates travel ideas based on user preferences
    using the Google Gen AI SDK.
    """

    def __init__(self, api_key: Optional[str] = None, model_name: str = "gemini-2.0-flash"):
        """
        Initialize the TravelAgent.

        Args:
            api_key: Google Cloud API key. If None, tries to read from GOOGLE_API_KEY env var.
            model_name: The name of the model to use.
        """
        self.api_key = api_key or os.getenv("GOOGLE_API_KEY")
        if not self.api_key:
            raise ValueError("API key must be provided or set in GOOGLE_API_KEY environment variable.")
        
        self.client = genai.Client(api_key=self.api_key)
        self.model_name = model_name

    def generate_travel_idea(self, preferences: Dict[str, str]) -> str:
        """
        Generates a travel idea based on the provided preferences.

        Args:
            preferences: A dictionary containing user preferences.
                         Example: {"budget": "low", "climate": "warm", "activity": "hiking"}

        Returns:
            A string containing the travel recommendation.
        """
        
        prompt = f"""
        Act as an expert travel agent. Generate a unique and exciting travel idea based on the following user preferences:
        
        - Budget: {preferences.get('budget', 'Any')}
        - Climate: {preferences.get('climate', 'Any')}
        - Preferred Activities: {preferences.get('activity', 'Any')}
        - Duration: {preferences.get('duration', 'Any')}
        
        Provide a catchy title, a brief description of the destination, why it fits the preferences, and a suggested itinerary highlight.
        """

        try:
            response = self.client.models.generate_content(
                model=self.model_name,
                contents=prompt,
                config=types.GenerateContentConfig(
                    temperature=0.7,
                )
            )
            return response.text
        except Exception as e:
            return f"Error generating travel idea: {str(e)}"
