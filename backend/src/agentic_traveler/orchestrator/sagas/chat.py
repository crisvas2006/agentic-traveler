"""ChatSaga — wraps the existing ChatAgent. Owns ``CHAT`` turns and is the
dispatcher's default owner when nothing else claims the turn (AC-8)."""

from __future__ import annotations

import logging
import time
from typing import Any, Optional

from agentic_traveler.core.observability import traceable
from agentic_traveler.orchestrator.chat_agent import ChatAgent
from agentic_traveler.orchestrator.client_factory import get_client
from agentic_traveler.orchestrator.sagas.base import SagaResult, SagaState

logger = logging.getLogger(__name__)


class ChatSaga:
    """Conversational turns — greetings, banter, emotional support, recall."""

    name = "ChatSaga"

    def __init__(self, client: Any = None):
        self._client = client or get_client()
        self._chat_agent = ChatAgent(client=self._client)

    def should_activate(
        self,
        intent: str,
        entities: dict[str, Any],
        trip: Optional[dict[str, Any]],
        state: SagaState,
    ) -> tuple[bool, bool]:
        if intent == "CHAT":
            return True, True
        return False, False

    @traceable(name="saga.chat.run")
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
        try:
            result = self._chat_agent.process_request(
                user_doc=user_doc,
                message=message,
                conversation_context=conversation_context,
                current_time=state.get("current_time", ""),
                preference_raw=state.get("preference_raw"),
                events=events,
            )
        except Exception:
            logger.exception("ChatSaga delegate to ChatAgent failed.")
            events.emit("metric", {"name": "error_raised", "saga": self.name})
            events.emit("metric", {
                "name": "saga_exited", "saga": self.name, "outcome": "error",
                "latency_ms": (time.time() - t) * 1000,
            })
            return SagaResult(
                text="Sorry, something glitched on my end. Mind trying that again?"
            )

        events.emit("metric", {
            "name": "saga_exited", "saga": self.name, "outcome": "ChatAgent",
            "latency_ms": (time.time() - t) * 1000,
        })
        return SagaResult(
            text=result.get("text", ""),
            _raw_response=result.get("_raw_response"),
            _latency_ms=result.get("_latency_ms", 0.0),
            _search_responses=result.get("_search_responses", []) or [],
        )
