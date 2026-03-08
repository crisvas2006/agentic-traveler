"""
Utility to extract a concise text summary from a Firestore user document.

The Firestore ``user_profile`` map mirrors the Tally intake form.  This
module turns it into a short narrative that any LLM agent can consume
without needing to know the raw field names.
"""

from typing import Dict, Any


def build_profile_summary(user_doc: Dict[str, Any]) -> str:
    """
    Convert a raw Firestore user document into a concise text block
    suitable for LLM prompts.

    Now specifically tailored to read the outputs of the ProfileAgent:
    - tags
    - additional_info
    - summary
    - extreme personality_dimensions_scores
    """
    name = user_doc.get("name", user_doc.get("user_name", "Traveler"))
    profile = user_doc.get("user_profile", {})
    extras = user_doc.get("learned_extras", {})
    conv_summary = user_doc.get("conversation_history", {}).get("summary", "")

    parts = [f"Name: {name}"]
    
    # Check if this is a newly structured profile or legacy form data
    if "personality_dimensions_scores" in profile or "summary" in profile:
        # --- New Intelligent Profile Structure ---
        if profile.get("summary"):
            parts.append(f"Profile Summary: {profile['summary']}")
            
        if profile.get("tags"):
            tags = profile["tags"]
            parts.append(f"Tags: {', '.join(tags) if isinstance(tags, list) else tags}")
            
        if profile.get("tone_preference"):
            parts.append(f"Tone/Communication Preference: {profile['tone_preference']}")
            
        if profile.get("additional_info"):
            parts.append(f"Additional Info/Constraints: {profile['additional_info']}")
            
        # Extract and explain extreme personality scores
        scores = profile.get("personality_dimensions_scores", {})
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
                
    else:
        # --- Legacy Fallback (just basic info if no profile agent ran yet) ---
        parts.append("\n(Legacy Profile - waiting for ProfileAgent update)")
        if profile.get("location"):
            parts.append(f"Home base: {profile['location']}")
        if profile.get("trip_vibe"):
            vibes = profile["trip_vibe"]
            parts.append(f"Trip vibes: {', '.join(vibes) if isinstance(vibes, list) else vibes}")
        if profile.get("absolute_avoidances"):
            avoids = profile["absolute_avoidances"]
            parts.append(f"Avoids: {', '.join(avoids) if isinstance(avoids, list) else avoids}")

    # --- agent-learned preferences (manual fallbacks outside the profile agent) ---
    if extras:
        parts.append("\nAgent-learned preferences:")
        for k, v in extras.items():
            parts.append(f"  {k}: {v}")

    # --- conversation history summary ---
    if conv_summary:
        parts.append(f"\nConversation history summary:\n{conv_summary}")

    return "\n".join(parts)
