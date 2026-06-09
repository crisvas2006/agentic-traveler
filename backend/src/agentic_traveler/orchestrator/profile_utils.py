"""
Utility to extract a concise text summary from a Supabase user document.

The ``user_profile`` map mirrors the Tally intake form and the output of
ProfileAgent.  This module turns it into a short narrative that any LLM
agent can consume without needing to know the raw field names.
"""

from typing import Dict, Any


def build_profile_summary(
    user_doc: Dict[str, Any],
    include_scores: bool = True,
    include_summary: bool = True,
) -> str:
    """
    Convert a raw user document into a concise text block suitable for LLM prompts.

    Tailored to read the outputs of the ProfileAgent and custom user preferences stored
    in the database `user_profiles.profile_data`.
    """
    name = user_doc.get("name", user_doc.get("user_name", "Traveler"))
    profile = user_doc.get("user_profile", {})
    profile_data = profile.get("profile_data") or {}

    # Gather data from profile_data (which is the direct database representation)
    summary = profile.get("summary")
    tags = profile_data.get("tags")
    tone_pref = profile_data.get("tone_preference")
    add_info = profile_data.get("additional_info")
    scores = profile_data.get("personality_dimensions_scores", {})
    hard_overrides = profile_data.get("hard_overrides") or []
    reply_length_pref = profile_data.get("reply_length_preference")

    parts = [f"Name: {name}"]

    # 1. Profile Summary
    if include_summary and summary:
        parts.append(f"Profile Summary: {summary}")

    # 1b. Hard overrides — slots the saga layer must NEVER ask about (Task 36).
    override_labels = []
    for o in hard_overrides:
        if isinstance(o, dict):
            slot = (o.get("slot") or "").removeprefix("ask.")
            value = o.get("value")
            if slot:
                override_labels.append(f"{slot}={value}" if value is not None else slot)
    if override_labels:
        parts.append(f"Never ask about (fixed): {', '.join(override_labels)}")

    # 1c. Reply length preference.
    if reply_length_pref:
        parts.append(f"Reply length preference: {reply_length_pref}")

    # 2. Tags
    if tags:
        parts.append(f"Tags: {', '.join(tags) if isinstance(tags, list) else tags}")

    # 3. Tone/Communication Preference
    if tone_pref:
        parts.append(f"Tone/Communication Preference: {tone_pref}")

    # 4. Additional Info/Constraints
    if add_info:
        parts.append(f"Additional Info/Constraints: {add_info}")

    # 5. Strong Personality Dimensions (if include_scores is True)
    if include_scores and scores:
        high_traits = []
        low_traits = []
        for dim, val in scores.items():
            try:
                val = float(val)
                if val >= 0.7:
                    high_traits.append(f"{dim} ({val})")
                elif val <= 0.3:
                    low_traits.append(f"{dim} ({val})")
            except (ValueError, TypeError):
                continue
        if high_traits or low_traits:
            parts.append("\nStrong Personality Dimensions (0.0 to 1.0 scale):")
            if high_traits:
                parts.append(f"  High (>0.7): {', '.join(high_traits)}")
            if low_traits:
                parts.append(f"  Low (<0.3): {', '.join(low_traits)}")

    # 6. Gather all other key-value preferences stored in profile_data
    known_keys = {
        "summary", "tags", "tone_preference", "additional_info",
        "personality_dimensions_scores", "short_summary",
        "hard_overrides", "reply_length_preference",
    }
    extra_prefs = {
        k: v for k, v in profile_data.items()
        if k not in known_keys and v is not None and v != "" and v != []
    }

    # Also check if there are flat keys directly under profile that are not in profile_data
    # (just in case they exist, though in the new design they are stored in profile_data)
    for k, v in profile.items():
        if k not in ("profile_data", "form_response", "summary") and k not in known_keys:
            if v is not None and v != "" and v != []:
                if k not in extra_prefs:
                    extra_prefs[k] = v

    def _format_value(value: Any, indent_level: int = 1) -> str:
        indent = "  " * indent_level
        if isinstance(value, dict):
            sub_parts = []
            for sub_k, sub_v in sorted(value.items()):
                sub_parts.append(f"\n{indent}{sub_k}: {_format_value(sub_v, indent_level + 1)}")
            return "".join(sub_parts)
        elif isinstance(value, list):
            return ", ".join(str(item) for item in value)
        else:
            return str(value)

    if extra_prefs:
        parts.append("\nUser Preferences:")
        for k, v in sorted(extra_prefs.items()):
            val_str = _format_value(v, 2)
            parts.append(f"  {k}: {val_str}")

    return "\n".join(parts)
