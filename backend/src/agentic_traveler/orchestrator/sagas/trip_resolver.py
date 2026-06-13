"""``resolve_active_trip`` — pick which trip a turn is about, from lightweight
trip *summaries* (task 36 §4.1 #1). The orchestrator then hydrates only the
chosen trip via ``TripRepository.get_trip()`` — never loads every trip in full.

Priority (proposal §5.5):
  1. the user explicitly names a trip (its title text appears in the message)
  2. active trip   (status == 'active')
  3. ready trip    (status == 'ready')
  4. most recently updated trip
"""

from __future__ import annotations

import datetime
from typing import Any, Optional

# Tokens that are too generic to identify a trip by name.
_STOPWORDS = frozenset({
    "trip", "the", "a", "an", "to", "my", "our", "and", "of", "in", "for",
    "plan", "planning", "vacation", "holiday", "escape", "getaway",
})


def is_established(summary: dict[str, Any]) -> bool:
    """True for a trip with real planning behind it — one we should not silently
    clobber or regenerate. Works off the cheap summary fields
    (`list_trip_summaries` selects no child rows): a non-DREAMING status or a
    populated ``vision_summary`` both signal an established trip."""
    status = (summary.get("status") or "").strip().lower()
    if status and status not in ("dreaming", "draft"):
        return True
    return bool((summary.get("vision_summary") or "").strip())


def resolve_trip_focus(
    summaries: list[dict[str, Any]],
    message: str,
    entities: Optional[dict[str, Any]],
    directive: str,
    focused_trip_id: Optional[str] = None,
) -> tuple[Optional[dict[str, Any]], Optional[str], bool]:
    """Decide which trip a planning turn is about, honouring the Router's
    ``trip_directive`` (task 44) and the frontend's ``focused_trip_id`` (the trip
    open in the dashboard TripPanel — task 52).

    Returns ``(chosen_summary, superseded_title, create_new)``. Resolution layers,
    in priority order:
      1. ``directive == "new"`` → ``(None, <most-recent established title or None>,
         True)`` — ignore existing trips; a fresh one is created downstream.
      2. **Destination match** (zero token cost): when the router already
         extracted ``entities.destinations`` and one or more trips carry a
         matching destination name / title, focus that trip — drifting away from
         ``focused_trip_id`` only when the message clearly points elsewhere
         (AC-6). Multiple matches are tie-broken by recency-of-relevance (AC-7).
      3. **Frontend focus**: the ``focused_trip_id`` trip, when it belongs to the
         user (a stale/forged id is ignored — AC-8).
      4. **Heuristic**: the pre-existing ``resolve_active_trip`` (active → ready →
         most-recent), which may return ``None`` — answering without forcing focus.
    """
    if directive == "new":
        established = [s for s in summaries if is_established(s)] if summaries else []
        prior = _most_recent(established) if established else None
        return None, (prior.get("title") if prior else None), True

    summaries = summaries or []
    dests = [
        d.strip().lower()
        for d in ((entities or {}).get("destinations") or [])
        if isinstance(d, str) and d.strip()
    ]
    if dests:
        matches = [s for s in summaries if _summary_matches_destinations(s, dests)]
        if matches:
            # No-jolt: when the already-focused trip is itself a match, keep it
            # (don't remount the panel); only switch when the message points at a
            # different trip (AC-6).
            if focused_trip_id:
                focused_match = next(
                    (s for s in matches if s.get("id") == focused_trip_id), None
                )
                if focused_match:
                    return focused_match, None, False
            return _tiebreak(matches), None, False

    if focused_trip_id:
        focused = next(
            (s for s in summaries if s.get("id") == focused_trip_id), None
        )
        if focused:  # AC-8: a focus id not among the user's trips is ignored.
            return focused, None, False

    return resolve_active_trip(summaries, message, entities), None, False


def _summary_matches_destinations(
    summary: dict[str, Any], dests_lower: list[str]
) -> bool:
    """True when any router-extracted destination matches the trip's destination
    names or its title (case-insensitive substring, both directions). Empty
    candidates are skipped so a title-less trip never matches everything."""
    candidates = [
        (d.get("name") or "").strip().lower()
        for d in (summary.get("destinations") or [])
    ]
    title = (summary.get("title") or "").strip().lower()
    if title:
        candidates.append(title)
    candidates = [c for c in candidates if c]
    for d in dests_lower:
        for c in candidates:
            if d == c or d in c or c in d:
                return True
    return False


def _tiebreak(matches: list[dict[str, Any]]) -> dict[str, Any]:
    """Pick one trip from several destination matches (AC-7): an ``active`` trip
    wins (it's underway) → else the nearest upcoming ``reference_date`` → else the
    most recent past one → else the most-recently-updated (deterministic)."""
    if len(matches) == 1:
        return matches[0]
    actives = [s for s in matches if (s.get("status") or "").lower() == "active"]
    if actives:
        return _most_recent(actives)
    today = datetime.date.today().isoformat()
    dated = [s for s in matches if s.get("reference_date")]
    upcoming = [s for s in dated if (s.get("reference_date") or "") >= today]
    if upcoming:
        return min(upcoming, key=lambda s: s.get("reference_date") or "")
    past = [s for s in dated if (s.get("reference_date") or "") < today]
    if past:
        return max(past, key=lambda s: s.get("reference_date") or "")
    return _most_recent(matches)


def resolve_active_trip(
    summaries: list[dict[str, Any]], message: str, entities: dict[str, Any] = None
) -> Optional[dict[str, Any]]:
    """Return the summary dict of the trip this turn is about, or None."""
    if not summaries:
        return None
    lower = message.lower()

    # 1. explicit name match — a non-trivial token of a trip title in the message
    for summary in summaries:
        if _title_matches(summary.get("title"), lower):
            return summary

    # 2. active
    actives = [s for s in summaries if s.get("status") == "active"]
    if actives:
        chosen = _most_recent(actives)
        if _is_destination_mismatch(chosen, entities):
            return None
        return chosen

    # 3. ready
    ready = [s for s in summaries if s.get("status") == "ready"]
    if ready:
        chosen = _most_recent(ready)
        if _is_destination_mismatch(chosen, entities):
            return None
        return chosen

    # 4. most recently updated
    chosen = _most_recent(summaries)
    if _is_destination_mismatch(chosen, entities):
        return None
    return chosen


def _title_matches(title: Optional[str], message_lower: str) -> bool:
    if not title:
        return False
    # The first comma-segment is usually the place, e.g. "Iceland, winter escape".
    head = title.split(",")[0].strip().lower()
    tokens = [t for t in head.split() if t not in _STOPWORDS]
    if not tokens:
        # Title is entirely generic ("My trip") — not identifying.
        return False
    if len(head) >= 4 and head in message_lower:
        return True
    for token in tokens:
        if len(token) >= 4 and token in message_lower:
            return True
    # A single short place-name token, e.g. "Goa".
    if len(tokens) == 1 and len(tokens[0]) >= 3 and tokens[0] in message_lower:
        return True
    return False


def _most_recent(items: list[dict[str, Any]]) -> dict[str, Any]:
    return max(
        items,
        key=lambda s: (s.get("updated_at") or "", s.get("reference_date") or ""),
    )


def _is_destination_mismatch(trip_summary: dict[str, Any], entities: Optional[dict[str, Any]]) -> bool:
    """Returns True if the entities contain explicit destinations and NONE of them match the trip title/destination."""
    if not entities:
        return False
    destinations = entities.get("destinations")
    if not destinations or not isinstance(destinations, list):
        return False
    
    trip_title = trip_summary.get("title") or ""
    if not trip_title:
        return False
        
    title_lower = trip_title.lower()
    for dest in destinations:
        dest_lower = dest.lower()
        if dest_lower in title_lower or title_lower in dest_lower:
            return False
            
    # We have explicit destinations but none matched the active trip's title
    return True
