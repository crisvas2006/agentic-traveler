"""Destination brief (task 45) — a compact, cached "world facts" knowledge
brief about a destination, captured ONCE when a destination is first set on a
trip, so advisory turns can ground their insight (best windows, seasonal
character, signature experiences) instead of asking blank slot questions.

Mirrors the country-intel "cached world facts, never authoritative" pattern
(task 38): captured once, refreshed only on explicit request, every render
carries a verify-with-official-sources disclaimer.

Storage: ``trip.discovery.destination_brief`` (the trips table has no
dedicated column; ``discovery`` is the planning JSONB bag). The column is
merge-replaced on write, so ``ensure_brief`` returns a SideEffect carrying the
full merged ``discovery`` dict.
"""

from __future__ import annotations

import json
import logging
import time
from datetime import datetime, timezone
from typing import Any, Optional

from google.genai import types

from agentic_traveler.core.observability import traceable
from agentic_traveler.orchestrator.client_factory import gemini_generate
from agentic_traveler.orchestrator.profile_utils import build_profile_summary
from agentic_traveler.orchestrator.sagas.base import SideEffect

logger = logging.getLogger(__name__)

_MODEL = "gemini-3.5-flash"

_SYSTEM_PROMPT = """\
You produce a compact destination knowledge brief for a travel advisor.
Facts must be broadly true, seasonal patterns conventional wisdom — this is
cached guidance, NEVER authoritative; downstream UI adds a "verify with
official sources" disclaimer. No visa/medical/legal claims.
Seasonality framework: for each window reason over the triad WEATHER /
CROWDS / PRICE; prefer naming shoulder windows (weeks adjacent to peak that
keep most of the weather and shed most of the crowds and cost).
fit_hooks: 3-6 short tags of what this destination rewards (e.g.
"slow-mornings", "hiker", "design-lover"), ordered by relevance to the
traveler profile provided. why-lines: one sentence, sensory and specific,
no superlative chains. Return ONLY the JSON object.
"""


def _schema() -> types.Schema:
    S, T = types.Schema, types.Type
    window = S(type=T.OBJECT, properties={
        "months": S(type=T.ARRAY, items=S(type=T.STRING)),
        "why": S(type=T.STRING),
        "crowd_level": S(type=T.STRING, nullable=True),
        "price_level": S(type=T.STRING, nullable=True),
    })
    avoid = S(type=T.OBJECT, properties={
        "months": S(type=T.ARRAY, items=S(type=T.STRING)),
        "why": S(type=T.STRING),
    })
    return S(type=T.OBJECT, properties={
        "destination": S(type=T.STRING),
        "best_windows": S(type=T.ARRAY, items=window),
        "avoid_windows": S(type=T.ARRAY, items=avoid),
        "seasonal_character": S(type=T.OBJECT, nullable=True, properties={
            "peak": S(type=T.STRING, nullable=True),
            "shoulder": S(type=T.STRING, nullable=True),
            "low": S(type=T.STRING, nullable=True),
        }),
        "signature_experiences": S(type=T.ARRAY, items=S(type=T.STRING)),
        "fit_hooks": S(type=T.ARRAY, items=S(type=T.STRING)),
    })


def _utcnow_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _primary_destination(trip: dict[str, Any]) -> Optional[str]:
    dests = (trip or {}).get("destinations") or []
    confirmed = next((d for d in dests if d.get("status") == "confirmed"), None)
    chosen = confirmed or (dests[0] if dests else None)
    name = (chosen or {}).get("name")
    return name.strip() if isinstance(name, str) and name.strip() else None


@traceable(name="saga.destination_brief.capture")
def capture_destination_brief(
    client: Any, destination: str, user_doc: dict[str, Any]
) -> Optional[dict[str, Any]]:
    """One flash structured-output call → the brief dict, or ``None`` on any
    failure (never raises). fit_hooks are ranked against the traveler's DNA
    summary at capture time (briefs are trip-scoped, so personalisation is OK)."""
    if client is None or not (destination or "").strip():
        return None
    dna = build_profile_summary(user_doc or {}, include_scores=False)
    user_content = (
        f"<destination>{destination}</destination>\n"
        f"<traveler_profile>{dna}</traveler_profile>"
    )
    try:
        raw = gemini_generate(
            client,
            model=_MODEL,
            contents=user_content,
            config=types.GenerateContentConfig(
                system_instruction=_SYSTEM_PROMPT,
                max_output_tokens=700,
                response_mime_type="application/json",
                response_schema=_schema(),
                automatic_function_calling=types.AutomaticFunctionCallingConfig(disable=True),
            ),
        )
        data = json.loads(raw.text or "{}")
    except Exception:
        logger.warning("destination brief capture failed for %s.", destination[:60], exc_info=True)
        return None
    if not isinstance(data, dict) or not data.get("best_windows"):
        return None
    data["destination"] = data.get("destination") or destination
    data["captured_at"] = _utcnow_iso()
    data["model_version"] = _MODEL
    return data


@traceable(name="saga.destination_brief.ensure")
def ensure_brief(
    client: Any, trip: dict[str, Any], user_doc: dict[str, Any], events: Any
) -> Optional[SideEffect]:
    """Idempotent. Returns a ``trip_patch`` SideEffect writing
    ``discovery.destination_brief`` iff a destination exists and no brief is
    stored for THAT destination; emits ``brief_captured``. Returns ``None``
    (no write, no metric) when a brief for the current destination already
    exists, or when there's no destination."""
    destination = _primary_destination(trip)
    if not destination:
        return None
    discovery = dict((trip or {}).get("discovery") or {})
    existing = discovery.get("destination_brief") or {}
    if existing.get("destination") == destination:
        return None  # already captured for this destination — idempotent

    t = time.time()
    brief = capture_destination_brief(client, destination, user_doc)
    events.emit("metric", {
        "name": "brief_captured",
        "ok": brief is not None,
        "latency_ms": int((time.time() - t) * 1000),
    })
    if brief is None:
        return None
    discovery["destination_brief"] = brief
    return SideEffect(kind="trip_patch", payload={"id": (trip or {}).get("id"), "discovery": discovery})
