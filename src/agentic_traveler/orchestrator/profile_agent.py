"""
Profile Agent — responsible for interpreting user data into a structured personality profile.

Converts raw Tally form submissions or conversational preferences into a 
structured schema:
- personality_dimensions_scores (15 dimensions)
- tags
- additional_info
- summary

This agent does not send messages to the user directly, but provides the
orchestrator with updated structured data to store in Firestore, and optionally 
returns a short greeting for new users.
"""

import json
import logging
from typing import Any, Dict, Optional

from google import genai
from google.genai import types

from agentic_traveler.orchestrator.client_factory import get_client

logger = logging.getLogger(__name__)

# The 15 dimensions defined in travel_personality_dimensions.md
_DIMENSIONS_LIST = [
    "exploration_tolerance",
    "structure_preference",
    "social_energy",
    "activity_intensity",
    "cultural_curiosity",
    "spiritual_orientation",
    "comfort_threshold",
    "uncertainty_tolerance",
    "budget_elasticity",
    "environment_preference",
    "aesthetic_sensitivity",
    "depth_vs_breadth",
    "crowd_tolerance",
    "learning_orientation",
    "risk_appetite"
]

_PROFILE_SYSTEM_PROMPT = f"""\
You are an expert psychological travel profiler.
Your job is to read user data (from forms or chat) and output a JSON profile of their travel personality.

We measure travel personality across the following 15 dimensions (0.0 to 1.0):
{", ".join(_DIMENSIONS_LIST)}

Output ONLY valid JSON matching this schema exactly:
{{
  "personality_dimensions_scores": {{
    "exploration_tolerance": <float 0.0-1.0>,
    ... (all 15 dimensions)
  }},
  "tags": ["Tag1", "Tag2"], // A few short tags describing their vibe
  "tone_preference": "Any specific requests for how I should talk to them (e.g., 'formal', 'playful and snarky', 'depressive with comedy', 'just the facts')",
  "additional_info": "Any hard constraints or extra info (diet, budget limits, etc.)",
  "summary": "A comprehensive summary of this traveler's style, heavily referencing their specific traits, avoidances, and preferences",
  "greeting": "A short, punchy 1-sentence welcome message (ONLY if requested)"
}}

Guidelines:
- 0.0-0.3 = Strong preference for the left anchor of the trait
- 0.4-0.6 = Balanced or situational
- 0.7-1.0 = Strong preference for the right anchor of the trait
- "tags" should be descriptive and useful for quick matching.
- "summary" must be comprehensive and encompassing of all traits and references of the user, not just a brief sentence.
- "greeting" MUST be observational, not declarative. Do not say "You are an active explorer". Instead say things like: "I see you take interest in cultural immersion and your preferences point to spontaneous exploration!"
"""

class ProfileAgent:
    def __init__(self, client: Optional[genai.Client] = None):
        self._client = client or get_client()
        # Profiling doesn't need huge reasoning, flash is extremely fast and capable of JSON extraction
        self._model_name = "gemini-2.5-flash"

    def build_initial_profile(self, raw_form_data: Dict[str, Any]) -> Dict[str, Any]:
        """
        Processes a raw Tally form submission into a structured profile.
        Returns the new profile dictionary, including a 'greeting' key.
        """
        if not self._client:
            logger.warning("No Gemini client available for ProfileAgent.")
            return self._build_fallback()

        prompt = (
            "Please analyze the following raw form submission and generate a full "
            "travel personality profile JSON. INCLUDE a short, punchy 'greeting' string.\n\n"
            f"FORM DATA:\n{json.dumps(raw_form_data, indent=2)}"
        )

        return self._call_llm(prompt)

    def update_profile(
        self, new_preference: str, current_profile: Dict[str, Any]
    ) -> Dict[str, Any]:
        """
        Takes an existing structured profile and a new piece of conversational data,
        and returns an updated structured profile JSON. (No greeting needed).
        """
        if not self._client:
            logger.warning("No Gemini client available for ProfileAgent.")
            return current_profile

        # Ensure we only pass the structured parts to the LLM to save tokens
        # (Exclude raw form_response if it exists in the dict being passed in)
        context_profile = {
            "personality_dimensions_scores": current_profile.get("personality_dimensions_scores", {}),
            "tags": current_profile.get("tags", []),
            "tone_preference": current_profile.get("tone_preference", ""),
            "additional_info": current_profile.get("additional_info", ""),
            "summary": current_profile.get("summary", ""),
        }

        prompt = (
            "Please update the following existing travel profile based on the new preference "
            "revealed by the user. Adjust scores slightly if necessary, add relevant tags, and "
            "update the summary/additional_info to incorporate this fact. Do NOT include a greeting.\n\n"
            f"CURRENT PROFILE:\n{json.dumps(context_profile, indent=2)}\n\n"
            f"NEW PREFERENCE LEARNED:\n{new_preference}"
        )

        return self._call_llm(prompt)

    def _call_llm(self, prompt: str) -> Dict[str, Any]:
        """Calls the LLM and forces JSON output."""
        try:
            response = self._client.models.generate_content(
                model=self._model_name,
                contents=prompt,
                config=types.GenerateContentConfig(
                    system_instruction=_PROFILE_SYSTEM_PROMPT,
                    temperature=0.2, # Low temp for consistent JSON
                    response_mime_type="application/json",
                ),
            )
            
            raw_text = response.text if hasattr(response, 'text') else str(response)
            
            # The model is forced to application/json, so it should be valid
            result = json.loads(raw_text)
            
            # Ensure all 15 dimensions exist in some form
            scores = result.get("personality_dimensions_scores", {})
            for dim in _DIMENSIONS_LIST:
                if dim not in scores:
                    scores[dim] = 0.5 # Default to balanced if missing
            result["personality_dimensions_scores"] = scores
            
            return result
            
        except Exception as e:
            logger.exception("Failed to generate profile structure: %s", e)
            return self._build_fallback()

    def _build_fallback(self) -> Dict[str, Any]:
        """Returns a safe default structure if the LLM fails."""
        return {
            "personality_dimensions_scores": {dim: 0.5 for dim in _DIMENSIONS_LIST},
            "tags": ["New Traveler"],
            "tone_preference": "Friendly, helpful, and concise",
            "additional_info": "",
            "summary": "We are still learning about this traveler's preferences.",
            "greeting": "Welcome to Agentic Traveler! Your profile is linked."
        }
