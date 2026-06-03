"""
Profile Agent — responsible for interpreting user data into a structured personality profile.

Converts raw Tally form submissions or conversational preferences into a 
structured schema:
- personality_dimensions_scores (15 dimensions)
- tags
- additional_info
- summary

This agent does not send messages to the user directly, but provides the
orchestrator with updated structured data to store in Supabase (user_profiles),
and optionally returns a short greeting for new users.
"""

import json
import logging
from typing import Any, Dict, List, Optional, Tuple

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

_PROFILE_GUIDELINES = """\
Guidelines for travel personality dimensions (0.0 to 1.0 scale):
- 0.0-0.3 = Strong preference for the left anchor of the trait
- 0.4-0.6 = Balanced or situational
- 0.7-1.0 = Strong preference for the right anchor of the trait
- "tags" should be descriptive and useful for quick matching.
- "summary" must be comprehensive and encompassing of all traits and references of the user, not just a brief sentence.
"""

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
  "short_summary": "A 2-3 sentence condensed, compelling summary capturing the absolute heart and essence of their Traveler DNA. Written in a warm, highly insightful tone, ready to be sent to the user as their onboarding acknowledgment message. Do NOT include any introductory or meta-text."
}}

{_PROFILE_GUIDELINES}
"""


# Fields that are list-valued and should be merged (not overwritten).
LIST_FIELDS = {
    "trip_vibe",
    "absolute_avoidances",
    "travel_deal_breakers",
    "travel_motivations",
    "next_trip_outcome_goals",
    "typical_trip_lengths",
}


class ProfileAgent:
    def __init__(self, client: Optional[genai.Client] = None):
        self._client = client or get_client()
        # Profiling doesn't need huge reasoning, flash is extremely fast and capable of JSON extraction
        self._model_name = "gemini-3.1-flash-lite"

    def build_initial_profile(
        self,
        raw_form_data: Dict[str, Any],
        user_uuid: Optional[str] = None,
        token_records: Optional[List[Dict[str, Any]]] = None,
    ) -> Tuple[Dict[str, Any], Any, float]:
        """
        Processes a raw Tally form submission into a structured profile.
        Returns a tuple of (profile_dict, response, latency_ms).
        """
        if not self._client:
            logger.warning("No Gemini client available for ProfileAgent.")
            return self._build_fallback(), None, 0.0

        prompt = (
            "Please analyze the following raw form submission and generate a full "
            "travel personality profile JSON.\n\n"
            f"FORM DATA:\n{json.dumps(raw_form_data, indent=2)}"
        )

        return self._call_llm(prompt)

    def update_profile(
        self,
        new_preference: str,
        current_profile: Dict[str, Any],
    ) -> Tuple[Dict[str, Any], Any, float]:
        """
        Takes an existing structured profile and a new piece of conversational data,
        and returns an updated structured profile JSON, along with response and latency.
        """
        if not self._client:
            logger.warning("No Gemini client available for ProfileAgent.")
            return current_profile, None, 0.0

        # Ensure we only pass the structured parts to the LLM to save tokens
        # (Exclude raw form_response if it exists in the dict being passed in)
        context_profile = {
            "personality_dimensions_scores": current_profile.get("personality_dimensions_scores", {}),
            "tags": current_profile.get("tags", []),
            "tone_preference": current_profile.get("tone_preference", ""),
            "additional_info": current_profile.get("additional_info", ""),
            "summary": current_profile.get("summary", ""),
            "short_summary": current_profile.get("short_summary", ""),
        }

        prompt = (
            "Please update the following existing travel profile based on the new preference "
            "revealed by the user. Adjust scores if necessary, add relevant tags, and "
            "update the summary/additional_info to incorporate this fact. Return ONLY JSON with updated profile.\n\n"
            f"{_PROFILE_GUIDELINES}\n\n"
            f"CURRENT PROFILE:\n{json.dumps(context_profile, indent=2)}\n\n"
            f"NEW PREFERENCE LEARNED:\n{new_preference}"
        )

        return self._call_llm(prompt)

    def save_preference(
        self,
        key: str,
        value: str,
        user_doc: Dict[str, Any],
        user_id: str,
        _sync: bool = False,
        token_records: Optional[List[Dict[str, Any]]] = None,
    ) -> None:
        """
        Persist a preference extracted by the orchestrator by asynchronously
        (or synchronously if token_records is provided) updating the profile in Supabase.
        Updates key-value directly, then runs update_profile to update summary and scores coherently.
        """
        import threading
        from agentic_traveler.tools.db_client import get_db

        should_sync = _sync or (token_records is not None)

        def _async_update():
            try:
                # 1. Fetch current profile_data and summary from Supabase (or fallback to user_doc)
                res = get_db().table("user_profiles").select("profile_data, summary").eq("user_id", user_id).maybe_single().execute()
                current_profile = {}
                db_summary = ""
                if res and res.data:
                    current_profile = res.data.get("profile_data") or {}
                    db_summary = res.data.get("summary") or ""

                if not current_profile:
                    user_profile = user_doc.get("user_profile", {})
                    current_profile = user_profile.get("profile_data") or {}
                    db_summary = user_profile.get("summary") or ""
                    if not current_profile:
                        # Fallback to key-value pairs directly under user_profile
                        current_profile = {
                            k: v for k, v in user_profile.items()
                            if k not in ("profile_data", "form_response", "summary")
                        }

                # 2. Update/Merge preference locally
                if key in LIST_FIELDS:
                    current_val = current_profile.get(key)
                    if isinstance(current_val, list):
                        new_list = list(current_val)
                    elif current_val is not None:
                        new_list = [current_val]
                    else:
                        new_list = []

                    if value not in new_list:
                        new_list.append(value)
                    current_profile[key] = new_list
                else:
                    current_profile[key] = value

                # Make sure summary is present in current_profile context for LLM prompt
                if "summary" not in current_profile or not current_profile["summary"]:
                    current_profile["summary"] = db_summary

                # 3. Call update_profile to run LLM
                new_fact = f"The user indicated their '{key}' preference is: {value}"
                updated_structured_data, response, latency_ms = self.update_profile(
                    new_fact, dict(current_profile)
                )

                # Log and accumulate the usage at the caller boundary!
                usage = None
                if response:
                    from agentic_traveler.analytics import usage_tracker
                    usage = usage_tracker.log_and_accumulate(
                        agent_name="profile_agent",
                        model_name=self._model_name,
                        user_id=user_id,
                        response=response,
                        latency_ms=latency_ms,
                    )
                    if token_records is not None:
                        token_records.append({
                            "model_name": self._model_name,
                            "input_tokens": usage.get("input_tokens", 0),
                            "output_tokens": usage.get("output_tokens", 0),
                            "agent_name": "profile_agent",
                        })

                # Merge LLM output into current_profile
                current_profile.update(updated_structured_data)
                updated_summary = current_profile.pop("summary", "")

                # 4. Upsert the updated profile_data and summary into user_profiles
                get_db().table("user_profiles").upsert(
                    {
                        "user_id": user_id,
                        "profile_data": current_profile,
                        "summary": updated_summary,
                    }
                ).execute()

                # 5. Bill user immediately if token_records is None and response exists
                if token_records is None and response and usage:
                    from agentic_traveler.economy import credit_manager
                    billing_records = [{
                        "model_name": self._model_name,
                        "input_tokens": usage.get("input_tokens", 0),
                        "output_tokens": usage.get("output_tokens", 0),
                        "agent_name": "profile_agent",
                    }]
                    credit_manager.record_usage_and_bill(
                        user_id=user_id,
                        token_records=billing_records,
                        default_agent_name="profile_agent",
                        run_async=False,
                    )

                try:
                    logger.info(
                        "Updated profile structure with preference: %s = %s (sync=%s)", key, value, should_sync
                    )
                except (ValueError, TypeError):
                    pass

            except Exception:
                try:
                    logger.exception("Failed to update user profile structure.")
                except (ValueError, TypeError):
                    pass

        if should_sync:
            _async_update()
        else:
            thread = threading.Thread(target=_async_update)
            thread.start()

    def _call_llm(
        self,
        prompt: str,
    ) -> Tuple[Dict[str, Any], Any, float]:
        """Calls the LLM and forces JSON output. Returns (result, response, latency_ms)"""
        _max_retries = 2
        _retry_waits = [3, 6]
        
        for _attempt in range(_max_retries + 1):
            try:
                import time
                
                t0 = time.time()
                response = self._client.models.generate_content(
                    model=self._model_name,
                    contents=prompt,
                    config=types.GenerateContentConfig(
                        system_instruction=_PROFILE_SYSTEM_PROMPT,
                        response_mime_type="application/json",
                    ),
                )
                latency_ms = (time.time() - t0) * 1000
                
                raw_text = response.text if hasattr(response, 'text') else str(response)
                
                # The model is forced to application/json, so it should be valid
                result = json.loads(raw_text)
                
                # Ensure all 15 dimensions exist in some form
                scores = result.get("personality_dimensions_scores", {})
                for dim in _DIMENSIONS_LIST:
                    if dim not in scores:
                        scores[dim] = 0.5 # Default to balanced if missing
                result["personality_dimensions_scores"] = scores
                
                return result, response, latency_ms
                
            except Exception as e:
                is_429 = "429" in str(e) or "RESOURCE_EXHAUSTED" in str(e)
                if is_429 and _attempt < _max_retries:
                    wait = _retry_waits[_attempt]
                    logger.warning("ProfileAgent LLM 429 (attempt %d/%d). Retrying in %ds.", _attempt + 1, _max_retries + 1, wait)
                    import time
                    time.sleep(wait)
                else:
                    logger.exception("Failed to generate profile structure: %s", e)
                    return self._build_fallback(), None, 0.0
        
        return self._build_fallback(), None, 0.0

    def _build_fallback(self) -> Dict[str, Any]:
        """Returns a safe default structure if the LLM fails."""
        return {
            "personality_dimensions_scores": {dim: 0.5 for dim in _DIMENSIONS_LIST},
            "tags": ["New Traveler"],
            "tone_preference": "Friendly, helpful, and concise",
            "additional_info": "",
            "summary": "We are still learning about this traveler's preferences.",
            "short_summary": "We are still learning about your traveler preferences."
        }
