"""Saga dispatcher package (Task 36).

Each saga is a small slot-filling skill that owns one concern. State lives in
data (`SagaState`), never on the saga instance, so the shape maps 1:1 to a
future LangGraph migration without the runtime dependency today.
"""

from agentic_traveler.orchestrator.sagas.base import (
    BaseSaga,
    ChoiceOption,
    SagaResult,
    SagaState,
    SideEffect,
    SlotFillStatus,
    SlotRequest,
)
from agentic_traveler.orchestrator.sagas.dispatcher import SagaDispatcher

__all__ = [
    "BaseSaga",
    "ChoiceOption",
    "SagaResult",
    "SagaState",
    "SideEffect",
    "SlotFillStatus",
    "SlotRequest",
    "SagaDispatcher",
]
