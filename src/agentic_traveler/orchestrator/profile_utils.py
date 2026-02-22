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

    Includes Tally form data (``user_profile``), agent-learned extras
    (``learned_extras``), and the conversation history summary.
    """
    name = user_doc.get("user_name", "Traveler")
    profile = user_doc.get("user_profile", {})
    extras = user_doc.get("learned_extras", {})
    conv_summary = (
        user_doc.get("conversation_history", {}).get("summary", "")
    )

    parts = [f"Name: {name}"]

    # --- identity ---
    if profile.get("age_group"):
        parts.append(f"Age group: {profile['age_group']}")
    if profile.get("location"):
        parts.append(f"Home base: {profile['location']}")

    # --- lifestyle & energy ---
    for key, label in [
        ("daily_rhythm", "Daily rhythm"),
        ("weekday_energy", "Weekday energy"),
        ("activity_level", "Activity level"),
    ]:
        if profile.get(key):
            parts.append(f"{label}: {profile[key]}")

    # --- travel style ---
    if profile.get("trip_vibe"):
        vibes = profile["trip_vibe"]
        parts.append(f"Trip vibes: {', '.join(vibes) if isinstance(vibes, list) else vibes}")
    if profile.get("structure_preference"):
        parts.append(f"Structure: {profile['structure_preference']}")
    if profile.get("solo_travel_comfort"):
        parts.append(f"Solo comfort: {profile['solo_travel_comfort']}")

    # --- budget & constraints ---
    if profile.get("travel_budget_style"):
        parts.append(f"Budget style: {profile['travel_budget_style']}")
    if profile.get("budget_priority"):
        parts.append(f"Budget priority: {profile['budget_priority']}")
    if profile.get("typical_trip_lengths"):
        lengths = profile["typical_trip_lengths"]
        parts.append(f"Typical trip length: {', '.join(lengths) if isinstance(lengths, list) else lengths}")

    # --- personality ---
    if profile.get("personality_baseline"):
        parts.append(f"Personality: {profile['personality_baseline']}")
    if profile.get("discomfort_tolerance_score") is not None:
        parts.append(f"Discomfort tolerance: {profile['discomfort_tolerance_score']}/5")
    if profile.get("cultural_spiritual_importance"):
        parts.append(f"Spiritual interest: {profile['cultural_spiritual_importance']}")

    # --- hard avoidances ---
    avoidances = profile.get("absolute_avoidances", [])
    if avoidances:
        parts.append(f"Hard avoidances: {', '.join(avoidances)}")
    if profile.get("absolute_avoidances_other"):
        parts.append(f"Also avoids: {profile['absolute_avoidances_other']}")

    # --- diet / lifestyle ---
    if profile.get("diet_lifestyle_constraints"):
        parts.append(f"Diet/lifestyle: {profile['diet_lifestyle_constraints']}")

    # --- travel motivations & goals ---
    motivations = profile.get("travel_motivations", [])
    if motivations:
        parts.append(f"Travel motivations: {', '.join(motivations)}")
    goals = profile.get("next_trip_outcome_goals", [])
    if goals:
        parts.append(f"Next trip goals: {', '.join(goals)}")
    if profile.get("dream_trip_style"):
        parts.append(f"Dream trip: {profile['dream_trip_style']}")

    # --- past experience ---
    if profile.get("favorite_past_trip"):
        parts.append(f"Favorite past trip: {profile['favorite_past_trip']}")
    if profile.get("disliked_trip_patterns"):
        parts.append(f"Disliked patterns: {profile['disliked_trip_patterns']}")

    # --- deal breakers ---
    deal_breakers = profile.get("travel_deal_breakers", [])
    if deal_breakers:
        parts.append(f"Deal breakers: {', '.join(deal_breakers)}")

    # --- free-text extras ---
    if profile.get("extra_notes"):
        parts.append(f"Extra notes: {profile['extra_notes']}")

    # --- agent-learned preferences ---
    if extras:
        parts.append("\nAgent-learned preferences:")
        for k, v in extras.items():
            parts.append(f"  {k}: {v}")

    # --- conversation history summary ---
    if conv_summary:
        parts.append(f"\nConversation history summary:\n{conv_summary}")

    return "\n".join(parts)
