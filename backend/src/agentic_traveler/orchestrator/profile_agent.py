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

from agentic_traveler.orchestrator.client_factory import get_client, gemini_generate
from agentic_traveler.core.observability import traceable

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

Output ONLY valid JSON matching this schema:
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

The JSON may also include additional keys representing specific categories of travel preferences (e.g., "trip_vibe", "absolute_avoidances", "travel_deal_breakers", "travel_motivations", "typical_trip_lengths", "budget", "diet", etc.). When updating or merging profiles, preserve any such existing keys and update or add them as appropriate.

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

    @traceable(name="profile_agent.build_initial_profile")
    def build_initial_profile(
        self,
        raw_form_data: Dict[str, Any],
        user_uuid: Optional[str] = None,
        token_records: Optional[List[Dict[str, Any]]] = None,
    ) -> Tuple[Dict[str, Any], Any, float]:
        """
        Processes a raw Tally form submission into a structured profile.
        Returns a tuple of (profile_dict, response, latency_ms).

        NOTE on user_uuid:
        - If user_uuid is provided, this method fetches the user's existing profile from
          the database and prompts the LLM to intelligently merge the new onboarding
          data with the existing conversational preferences (resolving conflicts while
          preserving independent preferences).
        - Passing user_uuid does NOT trigger credit billing or database writes inside
          this method. Billing and saving of the returned structured profile are the
          caller's responsibility.
        """
        if not self._client:
            logger.warning("No Gemini client available for ProfileAgent.")
            return self._build_fallback(), None, 0.0

        existing_profile = {}
        if user_uuid:
            from agentic_traveler.tools.db_client import get_db
            try:
                res = get_db().table("user_profiles").select("profile_data, summary").eq("user_id", user_uuid).maybe_single().execute()
                if res and res.data:
                    existing_profile = res.data.get("profile_data") or {}
                    db_summary = res.data.get("summary") or ""
                    if db_summary and "summary" not in existing_profile:
                        existing_profile["summary"] = db_summary
            except Exception:
                logger.exception("Failed to fetch existing profile for user_uuid=%s inside build_initial_profile", user_uuid)

        fallback_base = {**self._build_fallback(), **existing_profile}

        if existing_profile:
            prompt = (
                "You are tasked with intelligently merging a new Tally onboarding form submission "
                "with the traveler's existing profile preferences.\n\n"
                "Here is the user's EXISTING PROFILE (which contains conversational/chat-learned preferences):\n"
                f"{json.dumps(existing_profile, indent=2)}\n\n"
                "Here is the NEW TALLY FORM SUBMISSION DATA:\n"
                f"{json.dumps(raw_form_data, indent=2)}\n\n"
                "INSTRUCTIONS FOR MERGING:\n"
                "1. If a preference in the existing profile directly conflicts with the new Tally form results "
                "(e.g., if the existing profile says the user likes a 'packed itinerary' but the new form "
                "indicates they prefer a 'relaxed/light itinerary', or they chose a different budget tier/vibe), "
                "the new onboarding form's results MUST override the old conflicting preference.\n"
                "2. If there are custom keys or specific preferences in the existing profile (like dietary "
                "restrictions, specific user-constructed preferences, or avoidances) that do NOT conflict "
                "with and are independent of the new form responses, you MUST preserve them in the final JSON.\n"
                "3. Re-calculate personality dimensions scores, tags, tone preferences, and update summaries to "
                "coherently incorporate both the new form data and the preserved existing preferences.\n"
                "4. Output the complete merged profile JSON. The JSON output must contain all standard fields "
                "(personality_dimensions_scores, tags, tone_preference, additional_info, summary, short_summary) "
                "plus any preserved custom keys from the existing profile."
            )
        else:
            prompt = (
                "Please analyze the following raw form submission and generate a full "
                "travel personality profile JSON.\n\n"
                f"FORM DATA:\n{json.dumps(raw_form_data, indent=2)}"
            )

        return self._call_llm(prompt, fallback_profile=fallback_base)

    @traceable(name="profile_agent.update_profile")
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

        # Exclude internal/database-only fields or large raw responses if they slip in
        context_profile = {
            k: v for k, v in current_profile.items()
            if k not in ("form_response",)
        }

        prompt = (
            "Please update the following existing travel profile based on the new preference "
            "revealed by the user.\n"
            "Analyze the new preference statement and intelligently merge it into the existing profile.\n"
            "INSTRUCTIONS:\n"
            "1. Update standard fields (personality_dimensions_scores, tags, tone_preference, additional_info, summary, short_summary) as appropriate.\n"
            "2. If the preference corresponds to standard custom keys (e.g. 'trip_vibe', 'absolute_avoidances', 'travel_deal_breakers', 'travel_motivations', 'typical_trip_lengths') or specific details like diet, budget, or other preferences, merge or update those keys directly in the profile JSON.\n"
            "3. If a new preference directly conflicts with an existing preference (e.g. 'User likes to have a packed itinerary' vs 'I want a light itinerary'), overwrite/update the old conflicting preference. Keep independent non-conflicting preferences.\n"
            "4. Return ONLY valid JSON containing the entire updated profile, preserving all non-conflicting custom and standard keys.\n\n"
            f"{_PROFILE_GUIDELINES}\n\n"
            f"CURRENT PROFILE:\n{json.dumps(context_profile, indent=2)}\n\n"
            f"NEW PREFERENCE LEARNED:\n{new_preference}"
        )

        return self._call_llm(prompt)

    def save_preference(
        self,
        preference_raw: str,
        user_doc: Dict[str, Any],
        user_id: str,
        _sync: bool = False,
        token_records: Optional[List[Dict[str, Any]]] = None,
    ) -> None:
        """
        Persist a preference extracted by the orchestrator by asynchronously
        (or synchronously if token_records is provided) updating the profile in Supabase.
        """
        import contextvars
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

                # Make sure summary is present in current_profile context for LLM prompt
                if "summary" not in current_profile or not current_profile["summary"]:
                    current_profile["summary"] = db_summary

                # 2. Call update_profile to run LLM
                updated_structured_data, response, latency_ms = self.update_profile(
                    preference_raw, dict(current_profile)
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

                # Merge LLM output into current_profile (retaining standard and custom keys)
                current_profile.update(updated_structured_data)
                updated_summary = current_profile.pop("summary", "")

                # 3. Upsert the updated profile_data and summary into user_profiles
                get_db().table("user_profiles").upsert(
                    {
                        "user_id": user_id,
                        "profile_data": current_profile,
                        "summary": updated_summary,
                    }
                ).execute()

                # 4. Bill user immediately if token_records is None and response exists
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

                logger.info(
                    "Updated profile structure with preference: %s (sync=%s)", preference_raw, should_sync
                )

            except Exception:
                logger.exception("Failed to update user profile structure.")

        if should_sync:
            _async_update()
        else:
            # Copy the current contextvars (including LangSmith trace context) so the
            # background thread appears as a nested child span, not an orphaned root trace.
            ctx = contextvars.copy_context()
            thread = threading.Thread(target=lambda: ctx.run(_async_update), daemon=True)
            thread.start()

    def _call_llm(
        self,
        prompt: str,
        fallback_profile: Optional[Dict[str, Any]] = None,
    ) -> Tuple[Dict[str, Any], Any, float]:
        """Calls the LLM and forces JSON output. Returns (result, response, latency_ms)"""
        _max_retries = 2
        _retry_waits = [3, 6]
        
        fallback = fallback_profile if fallback_profile is not None else self._build_fallback()
        
        for _attempt in range(_max_retries + 1):
            try:
                import time
                
                t0 = time.time()
                response = gemini_generate(
                    self._client,
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
                    return fallback, None, 0.0
        
        return fallback, None, 0.0

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
