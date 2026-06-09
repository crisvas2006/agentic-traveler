"""``derive_saga_state_local`` — Python mirror of ``public.derive_saga_state()``
(task 34). Parity with the SQL is asserted in tests.

Uses key-*presence* semantics (``"pace" in prefs``) to match the SQL
``preferences ? 'pace'`` operator exactly, not truthiness. The trip passed in
is a plain dict (``Trip.model_dump()``), so child collections (destinations,
bookings) are lists of dicts.
"""

from __future__ import annotations

from datetime import date
from typing import Any, Optional

STATES = (
    "DREAMING", "SHAPING", "ANCHORING", "DETAILING",
    "READY_TO_GO", "LIVING", "REMEMBERING",
)


def derive_saga_state_local(
    trip: Optional[dict[str, Any]], today: Optional[date] = None
) -> str:
    """Return the canonical saga phase for ``trip``. ``DREAMING`` if no trip."""
    if not trip:
        return "DREAMING"
    today = today or date.today()

    tf = (trip.get("discovery") or {}).get("timeframe") or {}
    start = _to_date(tf.get("start_date"))
    end = _to_date(tf.get("end_date"))

    # LIVING: today within [start, end]
    if start and end and start <= today <= end:
        return "LIVING"
    # REMEMBERING: ended within the last 30 days
    if end and today > end and (today - end).days <= 30:
        return "REMEMBERING"
    # READY_TO_GO: departure within 7 days
    if start and 0 <= (start - today).days <= 7:
        return "READY_TO_GO"

    dests = trip.get("destinations") or []
    confirmed = sum(1 for d in dests if d.get("status") == "confirmed")
    considered = sum(1 for d in dests if d.get("status") == "considering")

    prefs = trip.get("preferences") or {}
    travelers = trip.get("travelers") or {}
    slots_ok = (
        "pace" in prefs and "structure" in prefs
        and "budget_tier" in prefs and "count" in travelers
    )
    bookings = trip.get("bookings") or []

    # DETAILING: bookings exist OR all planning prerequisites met
    if bookings or (confirmed > 0 and slots_ok):
        return "DETAILING"
    # ANCHORING: destination confirmed + start date firm
    if confirmed > 0 and start:
        return "ANCHORING"
    # SHAPING: at least one destination considered or confirmed
    if confirmed > 0 or considered > 0:
        return "SHAPING"
    return "DREAMING"


def _to_date(value: Any) -> Optional[date]:
    if isinstance(value, date):
        return value
    if not value:
        return None
    try:
        return date.fromisoformat(str(value)[:10])
    except (ValueError, TypeError):
        return None
