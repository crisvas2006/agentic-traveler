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
    SagaResult,
    SagaState,
    SideEffect,
)
from agentic_traveler.orchestrator.trip_agent import TripAgent

logger = logging.getLogger(__name__)


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
