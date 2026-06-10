"""SagaDispatcher — deterministic Python selection of the owner saga plus any
listener sagas for a turn (Task 36 §5: no LLM round-trip for selection).

Selection walks the registered sagas in priority order. The first saga that
``wants_to_own_reply`` becomes the owner; sagas that can act but don't want to
own become listeners (they run first, for idempotent side effects). If nobody
claims ownership, ChatSaga is the default owner.
"""

from __future__ import annotations

from typing import Any, Optional

from agentic_traveler.orchestrator.sagas.base import BaseSaga, SagaState
from agentic_traveler.orchestrator.sagas.chat import ChatSaga
from agentic_traveler.orchestrator.sagas.discovery import DiscoverySaga
from agentic_traveler.orchestrator.sagas.off_topic import OffTopicSaga
from agentic_traveler.orchestrator.sagas.planning import PlanningSaga
from agentic_traveler.orchestrator.sagas.country_intel import CountryIntelSaga


class SagaDispatcher:
    """Holds the saga registry and selects owner + listeners per turn."""

    def __init__(self, client: Any = None):
        # Priority order: specialised owners first, ChatSaga last as fallback.
        self._sagas: list[BaseSaga] = [
            CountryIntelSaga(client),
            PlanningSaga(client),
            DiscoverySaga(client),
            OffTopicSaga(client),
            ChatSaga(client),
        ]
        # Future tasks register BookingInputSaga,
        # MoodCheckinSaga, JournalSaga, MemorySearchSaga here.

    @property
    def sagas(self) -> list[BaseSaga]:
        return self._sagas

    def select(
        self,
        intent: str,
        entities: dict[str, Any],
        trip: Optional[dict[str, Any]],
        state: SagaState,
    ) -> tuple[BaseSaga, list[BaseSaga]]:
        """Return ``(owner, listeners)``."""
        owner: Optional[BaseSaga] = None
        listeners: list[BaseSaga] = []
        for saga in self._sagas:
            can_act, wants_owner = saga.should_activate(intent, entities, trip, state)
            if not can_act:
                continue
            if wants_owner and owner is None:
                owner = saga
            elif not wants_owner:
                listeners.append(saga)
        if owner is None:
            owner = self._chat_saga()
        return owner, listeners

    def _chat_saga(self) -> BaseSaga:
        for saga in self._sagas:
            if saga.name == "ChatSaga":
                return saga
        # Registry always contains ChatSaga; this is defensive only.
        raise RuntimeError("SagaDispatcher: ChatSaga not registered.")
