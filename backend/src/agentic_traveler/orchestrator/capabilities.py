"""Capability → router-output map (Task 50) — the backend trust boundary.

The frontend capability registry (`frontend/src/lib/capabilities.ts`) is NOT
trusted. When the web client posts a ``capability`` id on /chat/send, the
orchestrator looks it up HERE and feeds the mapped router output (intent +
entities) straight into the normal ``SagaDispatcher``, skipping the RouterAgent
LLM call. Only *intent-kind* capabilities appear in this map; message-, draft-,
link-, and ephemeral-kind launches never carry a ``capability`` field.

Kept dependency-free so the chat router can validate ids at request time without
pulling the model client on cold start.

Sync rule: every intent-kind id in the frontend registry MUST have a key here.
Adding an intent-kind capability means adding it in both places (guarded by
``backend/tests/orchestrator/test_orchestrator.py``).
"""

from __future__ import annotations

from typing import Any

# id → the router output that makes the owning saga win in SagaDispatcher.select.
# Currently empty: `add_booking` was changed from intent-kind to draft-kind (the
# user pre-fills and sends the booking text manually). Add entries here when a
# new intent-kind capability is introduced.
CAPABILITY_INTENTS: dict[str, dict[str, Any]] = {}
