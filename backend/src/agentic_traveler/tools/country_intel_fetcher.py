"""Two-step fetcher: (1) grounded research with gemini-3.5-flash, (2)
structured extraction with gemini-3.1-flash-lite.

NEVER imports network helpers directly — always goes through SearchAgent
so we get grounding + citations consistently.
"""

import json
import logging
from datetime import datetime, timezone
from typing import Any, Optional

from google.genai import types

from agentic_traveler.orchestrator.search_agent import SearchAgent
from agentic_traveler.orchestrator.client_factory import get_client, gemini_generate
from agentic_traveler.analytics import usage_tracker
from agentic_traveler.core.observability import traceable

logger = logging.getLogger(__name__)

_RESEARCH_PROMPT = """\
You are researching travel-relevant facts for a single country: {country}.
Cover concisely: entry/visa rules, safety advisory, vaccine guidance,
currency and money habits, SIM/eSIM/wifi, plugs/voltage, transit, language,
climate for month {month}, and notable public holidays / festivals around
{month}. Be terse. Cite official sources. Do not invent.
"""

_STRUCTURE_PROMPT = """\
Extract the following research into this exact JSON schema. If a value is
unknown, use null. Do not invent.

{schema}

Research:
{research}
"""

_INTEL_SCHEMA = types.Schema(
    type=types.Type.OBJECT,
    properties={
        "entry": types.Schema(
            type=types.Type.OBJECT,
            properties={
                "visa_rule": types.Schema(type=types.Type.STRING, nullable=True),
                "validity": types.Schema(type=types.Type.STRING, nullable=True),
            },
            nullable=True,
        ),
        "safety": types.Schema(
            type=types.Type.OBJECT,
            properties={
                "advisory_level": types.Schema(type=types.Type.INTEGER, nullable=True),
                "crime_signal": types.Schema(type=types.Type.NUMBER, nullable=True),
                "summary": types.Schema(type=types.Type.STRING, nullable=True),
            },
            nullable=True,
        ),
        "health": types.Schema(
            type=types.Type.OBJECT,
            properties={
                "vaccines": types.Schema(
                    type=types.Type.ARRAY,
                    items=types.Schema(type=types.Type.STRING),
                    nullable=True,
                ),
                "water_safe": types.Schema(type=types.Type.BOOLEAN, nullable=True),
            },
            nullable=True,
        ),
        "money": types.Schema(
            type=types.Type.OBJECT,
            properties={
                "currency": types.Schema(type=types.Type.STRING, nullable=True),
                "card_acceptance": types.Schema(type=types.Type.STRING, nullable=True),
                "tipping": types.Schema(type=types.Type.STRING, nullable=True),
            },
            nullable=True,
        ),
        "connectivity": types.Schema(
            type=types.Type.OBJECT,
            properties={
                "esim_support": types.Schema(type=types.Type.BOOLEAN, nullable=True),
                "wifi_availability": types.Schema(type=types.Type.STRING, nullable=True),
            },
            nullable=True,
        ),
        "transport": types.Schema(
            type=types.Type.OBJECT,
            properties={
                "primary_mode": types.Schema(type=types.Type.STRING, nullable=True),
                "rideshare": types.Schema(type=types.Type.STRING, nullable=True),
            },
            nullable=True,
        ),
        "language": types.Schema(
            type=types.Type.OBJECT,
            properties={
                "primary": types.Schema(type=types.Type.STRING, nullable=True),
                "english_proficiency": types.Schema(type=types.Type.STRING, nullable=True),
            },
            nullable=True,
        ),
        "climate_by_month": types.Schema(
            type=types.Type.OBJECT,
            properties={
                "temp_range": types.Schema(type=types.Type.STRING, nullable=True),
                "rain_risk": types.Schema(type=types.Type.STRING, nullable=True),
                "summary": types.Schema(type=types.Type.STRING, nullable=True),
            },
            nullable=True,
        ),
        "calendar": types.Schema(
            type=types.Type.OBJECT,
            properties={
                "festivals": types.Schema(
                    type=types.Type.ARRAY,
                    items=types.Schema(type=types.Type.STRING),
                    nullable=True,
                ),
                "holidays": types.Schema(
                    type=types.Type.ARRAY,
                    items=types.Schema(type=types.Type.STRING),
                    nullable=True,
                ),
            },
            nullable=True,
        ),
        "sources": types.Schema(
            type=types.Type.ARRAY,
            items=types.Schema(type=types.Type.STRING),
            nullable=True,
        ),
    },
)

@traceable(name="country_intel.fetch")
def fetch_country_intel(iso_country: str, country_name: str, month_name: str) -> dict[str, Any]:
    """Fetches country intel via SearchAgent and structures it."""
    client = get_client()
    search_agent = SearchAgent(client=client)

    # 1. Grounded research (gemini-3.5-flash)
    prompt = _RESEARCH_PROMPT.format(country=country_name, month=month_name)
    logger.info("Fetching country intel for %s (%s)", country_name, iso_country)
    
    token_records = []
    
    research_text, search_raw, search_lat = search_agent.search_with_metadata(prompt, format="comprehensive", model="gemini-3.5-flash")
    
    if search_raw and hasattr(search_raw, "usage_metadata"):
        search_usage = usage_tracker.log_and_accumulate(
            agent_name="search",
            model_name="gemini-3.5-flash",
            user_id="system_background", # Will be overriden in billing
            response=search_raw,
            latency_ms=search_lat,
        )
        if search_usage.get("total_tokens", 0) > 0:
            token_records.append(search_usage)
            
        grounding_credits = search_usage.get("grounding_cost_credits", 0)
        if grounding_credits > 0:
            token_records.append({
                "model_name": "grounding",
                "input_tokens": 0,
                "output_tokens": 0,
                "total_tokens": 0,
                "grounding_cost_credits": grounding_credits,
            })

    # 2. Structure extraction (gemini-3.1-flash-lite)
    structure_prompt = _STRUCTURE_PROMPT.format(schema="See system instructions", research=research_text)
    
    import time
    t_start = time.time()
    try:
        response = gemini_generate(
            client,
            model="gemini-3.1-flash-lite",
            contents=structure_prompt,
            config=types.GenerateContentConfig(
                response_mime_type="application/json",
                response_schema=_INTEL_SCHEMA,
                temperature=0.0,
            ),
        )
        lat = (time.time() - t_start) * 1000
        snapshot = json.loads(response.text)
        
        if response and hasattr(response, "usage_metadata"):
            extract_usage = usage_tracker.log_and_accumulate(
                agent_name="intel_extractor",
                model_name="gemini-3.1-flash-lite",
                user_id="system_background",
                response=response,
                latency_ms=lat,
            )
            if extract_usage.get("total_tokens", 0) > 0:
                token_records.append(extract_usage)
                
    except Exception:
        logger.exception("Failed to structure country intel for %s", country_name)
        snapshot = {}

    snapshot["iso_country"] = iso_country
    snapshot["fetched_at"] = datetime.now(timezone.utc).isoformat()
    snapshot["fetcher_version"] = "1.0"
    
    # Calculate safety score
    advisory_level = snapshot.get("safety", {}).get("advisory_level") if isinstance(snapshot.get("safety"), dict) else None
    crime_signal = snapshot.get("safety", {}).get("crime_signal") if isinstance(snapshot.get("safety"), dict) else None
    
    score = compute_safety_score_10(advisory_level, None, crime_signal)
    if score is not None:
        if not snapshot.get("safety"):
            snapshot["safety"] = {}
        snapshot["safety"]["score_10"] = score

    snapshot["_token_records"] = token_records

    return snapshot

def compute_safety_score_10(advisory_level: Optional[int], gpi_rank: Optional[int],
                            crime_signal: Optional[float]) -> Optional[float]:
    if advisory_level is None and gpi_rank is None:
        return None
    # Advisory: 1→10, 2→7, 3→4, 4→1 (linear-ish, capped)
    adv = {1:10.0, 2:7.0, 3:4.0, 4:1.0}.get(advisory_level, 7.0)
    # GPI: top50 → +1.5, top100 → 0, bottom 50 → -1.5
    gpi = 0.0
    if gpi_rank is not None:
        if gpi_rank <= 50:
            gpi = +1.5
        elif gpi_rank > 110:
            gpi = -1.5
    # Crime: weight 0.5
    crime = -0.5 * (crime_signal or 0.0)
    return max(0.0, min(10.0, adv + gpi + crime))

def user_threshold(profile: dict[str, Any]) -> float:
    risk = (profile.get("personality_dimensions_scores") or {}).get("risk_appetite", 0.5)
    if risk >= 0.7:
        return 5.0
    if risk <= 0.3:
        return 8.0
    return 7.0
