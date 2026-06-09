"""OffTopicSaga — owns ``OFF_TOPIC`` turns at the dispatcher level (AC-8).

The off-topic *counter* and restriction enforcement remain in the orchestrator
(``off_topic_guard``), which short-circuits OFF_TOPIC before dispatch today.
This saga exists so the dispatcher is complete and so task 37 can migrate the
OFF_TOPIC path onto the saga surface without a new abstraction. Its ``run``
returns a warm, canned redirect (no LLM call) and emits no side effects.
"""

from __future__ import annotations

import time
from typing import Any, Optional

from agentic_traveler.core.observability import traceable
from agentic_traveler.orchestrator.sagas.base import SagaResult, SagaState

_REDIRECT = (
    "I'm really only built for travel — trips, destinations, planning, that "
    "kind of thing. What's on your mind travel-wise? (Heads up: repeated "
    "off-topic messages can pause the chat for a bit.)"
)


class OffTopicSaga:
    """Redirects clearly non-travel turns back to travel."""

    name = "OffTopicSaga"

    def __init__(self, client: Any = None):
        self._client = client

    def should_activate(
        self,
        intent: str,
        entities: dict[str, Any],
        trip: Optional[dict[str, Any]],
        state: SagaState,
    ) -> tuple[bool, bool]:
        if intent == "OFF_TOPIC":
            return True, True
        return False, False

    @traceable(name="saga.off_topic.run")
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
        events.emit("metric", {
            "name": "saga_exited", "saga": self.name, "outcome": "redirect",
            "latency_ms": (time.time() - t) * 1000,
        })
        return SagaResult(text=state.get("router_response") or _REDIRECT)
