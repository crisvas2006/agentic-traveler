"""DiscoverySaga — owns ``TRIP`` turns when the trip is still being discovered.

Delegates the reply to the existing TripAgent (a content engine) and, when the
router extracted destination candidates, stages them onto the trip as
``considering`` destinations so the trip starts taking shape.
"""

from __future__ import annotations

import logging
import time
from typing import Any, Optional

from agentic_traveler.core.observability import traceable
from agentic_traveler.orchestrator.client_factory import get_client
from agentic_traveler.orchestrator.sagas.base import (
    ChoiceOption,
    SagaResult,
    SagaState,
    SideEffect,
    SlotRequest,
)
from agentic_traveler.orchestrator.trip_agent import TripAgent

logger = logging.getLogger(__name__)

# Explicit "start planning now" phrases. Their presence is a clear go-signal:
# the orchestrator creates the trip directly (no confirmation needed — AC-14).
_GO_SIGNALS = (
    "let's plan", "lets plan", "let us plan", "start planning", "start a plan",
    "plan a trip", "plan my trip", "plan me a", "plan us a", "help me plan",
    "build an itinerary", "build me an itinerary", "make an itinerary",
    "make me an itinerary", "let's book", "lets book", "book it",
    "organize a trip", "organise a trip", "let's do it", "lets do it",
    "let's go ahead", "set it up",
)

# Softer "I'd like to travel there" cues — a desire to go without a command to
# plan. Paired with a named destination, these trigger a one-line confirmation
# before any trip is created (AC-14), so we never silently acquire a trip.
_SOFT_START_CUES = (
    "thinking of going", "thinking about going", "thinking of a trip",
    "thinking about a trip", "i want to go to", "i wanna go to",
    "i'd like to go to", "id like to go to", "i want to visit",
    "i'd like to visit", "id like to visit", "i'd love to visit",
    "i want to travel to", "hoping to visit", "hoping to go to",
    "dreaming of", "we want to go to", "we'd like to visit",
    "planning to visit", "planning to go to", "would love to go to",
)


def has_go_signal(message: str) -> bool:
    """True when the message contains an explicit "start planning now" phrase
    (task 52 AC-14). Used by the orchestrator to create a trip without asking."""
    m = (message or "").lower()
    return any(g in m for g in _GO_SIGNALS)


def _has_soft_start_cue(message: str) -> bool:
    """True for a soft desire-to-travel cue that warrants a create confirmation
    rather than silent creation (task 52 AC-14)."""
    m = (message or "").lower()
    return any(c in m for c in _SOFT_START_CUES)


class DiscoverySaga:
    """Open-ended destination discovery before a trip is shaped."""

    name = "DiscoverySaga"

    def __init__(self, client: Any = None):
        self._client = client or get_client()
        self._trip_agent = TripAgent(client=self._client)

    def should_activate(
        self,
        intent: str,
        entities: dict[str, Any],
        trip: Optional[dict[str, Any]],
        state: SagaState,
    ) -> tuple[bool, bool]:
        # Owns TRIP turns only when there is no resolved trip yet; once a trip
        # exists, PlanningSaga takes over.
        if intent == "TRIP" and trip is None:
            return True, True
        return False, False

    @traceable(name="saga.discovery.run")
    def run(
        self,
        message: str,
        user_doc: dict[str, Any],
        trip: Optional[dict[str, Any]],
        state: SagaState,
        conversation_context: str,
        events: Any,
    ) -> SagaResult:
        t = time.time()
        events.emit("metric", {"name": "saga_entered", "saga": self.name})

        # AC-14: a soft desire-to-travel cue with no trip yet → confirm before
        # creating anything. Explicit go-signals don't reach here with trip=None
        # (the orchestrator already created the trip), and plain questions fall
        # through to a normal conversational answer (no nag).
        confirm = self._maybe_confirm_create(message, trip, state, events, t)
        if confirm is not None:
            return confirm

        side_effects = self._destination_effects(state, trip)

        try:
            result = self._trip_agent.process_request(
                user_doc=user_doc,
                message=message,
                conversation_context=conversation_context,
                current_time=state.get("current_time", ""),
                preference_raw=state.get("preference_raw"),
                events=events,
            )
        except Exception:
            logger.exception("DiscoverySaga delegate to TripAgent failed.")
            events.emit("metric", {"name": "error_raised", "saga": self.name})
            events.emit("metric", {
                "name": "saga_exited", "saga": self.name, "outcome": "error",
                "latency_ms": (time.time() - t) * 1000,
            })
            return SagaResult(
                text="Sorry, something glitched on my end. Mind trying that again?",
                side_effects=side_effects,
            )

        events.emit("metric", {
            "name": "saga_exited", "saga": self.name, "outcome": "TripAgent",
            "latency_ms": (time.time() - t) * 1000,
        })
        return SagaResult(
            text=result.get("text", ""),
            side_effects=side_effects,
            _raw_response=result.get("_raw_response"),
            _latency_ms=result.get("_latency_ms", 0.0),
            _search_responses=result.get("_search_responses", []) or [],
        )

    def _maybe_confirm_create(
        self,
        message: str,
        trip: Optional[dict[str, Any]],
        state: SagaState,
        events: Any,
        t: float,
    ) -> Optional[SagaResult]:
        """Return a one-line create confirmation (≤200 chars, CLAUDE.md §7.1) when
        the user softly signals wanting to start a trip but hasn't committed —
        otherwise ``None``. Stateless: the chip's reply re-classifies as PLAN next
        turn and the orchestrator creates the trip then (task 52 AC-14)."""
        if trip is not None:
            return None
        if has_go_signal(message) or not _has_soft_start_cue(message):
            return None
        destinations = [
            d for d in ((state.get("entities") or {}).get("destinations") or [])
            if isinstance(d, str) and d.strip()
        ]
        if not destinations:
            return None
        place = destinations[0].strip()[:60]
        prompt = f"Want me to start a trip for {place}?"
        events.emit("metric", {"name": "trip_create_confirm_offered", "saga": self.name})
        events.emit("metric", {
            "name": "saga_exited", "saga": self.name, "outcome": "confirm_create",
            "latency_ms": (time.time() - t) * 1000,
        })
        return SagaResult(
            text=prompt,
            slot_request=SlotRequest(
                slot="trip_create",
                prompt=prompt,
                choices=[
                    ChoiceOption("yes", f"Yes, plan {place}", f"Let's plan a trip to {place}."),
                    ChoiceOption("no", "Not yet", "Not yet — just exploring for now."),
                ],
            ),
        )

    @staticmethod
    def _destination_effects(
        state: SagaState, trip: Optional[dict[str, Any]]
    ) -> list[SideEffect]:
        if trip is None:
            return []
        trip_id = trip.get("id")
        if not trip_id:
            return []
        destinations = (state.get("entities") or {}).get("destinations") or []
        existing = {
            (d.get("name") or "").strip().lower()
            for d in (trip.get("destinations") or [])
        }
        effects: list[SideEffect] = []
        for name in destinations:
            if not isinstance(name, str) or not name.strip():
                continue
            if name.strip().lower() in existing:
                continue
            effects.append(SideEffect(
                kind="destination_upsert",
                payload={"trip_id": trip_id, "name": name.strip(), "status": "considering"},
            ))
        return effects
