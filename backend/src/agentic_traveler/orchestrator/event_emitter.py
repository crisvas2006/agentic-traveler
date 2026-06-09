"""EventEmitter — single sink interface, three phases (status, delta, metric).

Sagas and tools call `events.emit(phase, payload)`. The orchestrator routes
each phase to its concrete sink. Task 37 wires `status` and `delta` to SSE
and Telegram; this task wires `metric` to analytics_events.
"""

import logging
from collections import deque
from typing import Any, Callable

from agentic_traveler.analytics.event_sink import flush_metrics

logger = logging.getLogger(__name__)


class EventEmitter:
    def __init__(
        self,
        *,
        user_id: str | None,
        trip_id: str | None,
        on_status: Callable[[str], None] | None = None,
        on_delta: Callable[[str], None] | None = None,
    ):
        self.user_id = user_id
        self.trip_id = trip_id
        self._on_status = on_status
        self._on_delta = on_delta
        self._metric_buffer: deque[dict] = deque()

    def emit(self, phase: str, payload: dict[str, Any]) -> None:
        if phase == "status":
            if self._on_status:
                try:
                    # status payloads carry {"message": "<user-facing string>"}
                    self._on_status(payload.get("message", ""))
                except Exception:
                    logger.warning("status sink failed.", exc_info=True)
        elif phase == "delta":
            if self._on_delta:
                try:
                    # delta payloads carry {"text": "<token chunk>"}
                    self._on_delta(payload.get("text", ""))
                except Exception:
                    logger.warning("delta sink failed.", exc_info=True)
        elif phase == "metric":
            self._metric_buffer.append({
                "event_name": payload.get("name") or "unnamed",
                "user_id": self.user_id,
                "trip_id": self.trip_id,
                "payload": {k: v for k, v in payload.items() if k != "name"},
            })
        else:
            logger.debug("EventEmitter: unknown phase %s, dropping.", phase)

    def flush_metrics(self) -> None:
        if self._metric_buffer:
            rows = list(self._metric_buffer)
            self._metric_buffer.clear()
            flush_metrics(rows)
