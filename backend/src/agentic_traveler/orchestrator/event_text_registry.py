"""Static map: (phase, key) -> user-visible status string (Task 37).

The orchestrator renders intermediate status events ("Understanding your
question…", "Checking the weather…") from this table — no LLM call. A value of
``None`` means "emit no status for this phase/key" (e.g. plain ChatSaga turns
stay silent). ``text_for`` falls back to the phase-only entry when a specific
key isn't mapped.
"""

from __future__ import annotations

from typing import Optional

STATUS_TEXT: dict[tuple[str, Optional[str]], Optional[str]] = {
    ("router", None): "Understanding what you're asking…",
    ("saga_selected", "PlanningSaga"): "Picking up your trip…",
    ("saga_selected", "DiscoverySaga"): "Searching for places…",
    ("saga_selected", "CountryIntelSaga"): "Looking up the destination…",
    ("saga_selected", "BookingInputSaga"): "Reading your booking…",
    ("saga_selected", "ChatSaga"): None,        # silent — chat needs no status
    ("saga_selected", "OffTopicSaga"): None,    # silent
    ("tool", "check_weather"): "Checking the weather…",
    ("tool", "search_web"): "Searching the web…",
    ("tool", "country_intel_fetch"): "Looking up entry rules…",
    ("composing", None): "Writing the reply…",
}


def text_for(phase: str, key: Optional[str] = None) -> Optional[str]:
    """Return the status string for ``(phase, key)``, falling back to the
    phase-only entry. Returns ``None`` when no status should be shown."""
    if (phase, key) in STATUS_TEXT:
        return STATUS_TEXT[(phase, key)]
    return STATUS_TEXT.get((phase, None))
