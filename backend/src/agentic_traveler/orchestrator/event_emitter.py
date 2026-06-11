"""EventEmitter — single sink interface, three phases (status, delta, metric).

Sagas and tools call `events.emit(phase, payload)`. The orchestrator routes
each phase to its concrete sink. Task 37 wires `status` and `delta` to SSE
and Telegram; this task wires `metric` to analytics_events.
"""

import logging
import time
from collections import deque
from typing import Any, Callable, Optional

from agentic_traveler.analytics.event_sink import flush_metrics

logger = logging.getLogger(__name__)


class EventEmitter:
    def __init__(
        self,
        *,
        user_id: str | None,
        trip_id: str | None,
        on_status: Callable[[dict], None] | None = None,
        on_delta: Callable[[dict], None] | None = None,
    ):
        self.user_id = user_id
        self.trip_id = trip_id
        self._on_status = on_status
        self._on_delta = on_delta
        self._metric_buffer: deque[dict] = deque()
        self._turn_start: float = time.time()
        self._ttft_ms: Optional[float] = None

    @property
    def ttft_ms(self) -> Optional[float]:
        """Time-to-first-token in ms for streamed web turns; None for non-streaming."""
        return self._ttft_ms

    @property
    def is_streaming(self) -> bool:
        """True when a delta sink is wired (web SSE turn) — agents stream token
        deltas only then; Telegram / non-streaming turns leave it False."""
        return self._on_delta is not None

    def emit(self, phase: str, payload: dict[str, Any]) -> None:
        if phase == "status":
            if self._on_status:
                try:
                    # status payloads carry {"phase": <str>, "text": <str>, ...};
                    # the sink (SSE writer / Telegram editor) reads what it needs.
                    self._on_status(payload)
                except Exception:
                    logger.warning("status sink failed.", exc_info=True)
        elif phase == "delta":
            if self._ttft_ms is None:
                self._ttft_ms = (time.time() - self._turn_start) * 1000
            if self._on_delta:
                try:
                    # delta payloads carry {"text": "<token chunk>"}
                    self._on_delta(payload)
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
