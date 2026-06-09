"""BaseSaga + state-as-data types for the saga dispatcher (Task 36).

State-as-data invariant: a saga NEVER stores conversation state on ``self``.
Everything it needs arrives as arguments; everything it changes is returned in
a ``SagaResult`` (slot request, state delta, side effects). Slot-fill is a
*return value*, never an exception. This is the shape that maps 1:1 to a future
LangGraph migration.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Optional, Protocol, TypedDict, runtime_checkable


class SlotFillStatus(str, Enum):
    """Lifecycle of a single slot within a saga turn."""

    PENDING = "pending"   # not yet asked
    ASKED = "asked"       # question emitted this turn, awaiting an answer
    FILLED = "filled"     # value present on the trip
    SKIPPED = "skipped"   # satisfied by a hard override


class SagaState(TypedDict, total=False):
    """Per-turn value object. NOT persisted — rebuilt fresh each turn from trip
    data + the incoming message + router entities (see task 36 §4.1 #2)."""

    trip_id: Optional[str]
    intent: str
    entities: dict[str, Any]
    saga_name: str
    phase: str                 # derived saga_state: DREAMING..REMEMBERING
    pending_slot: Optional[str]
    slots_filled: dict[str, Any]
    message_text: str
    # task 44 — direction switching
    trip_directive: str                    # 'continue' | 'new' | 'unspecified'
    superseded_trip_title: Optional[str]   # title of a trip set aside by a 'new' turn


@dataclass(frozen=True)
class ChoiceOption:
    """One selectable option for a multiple-choice slot prompt.

    Absorbs ``task_chat_future_extensions.md`` §1 at the contract level. The
    rendering (web chips / Telegram inline keyboard) and the click → /chat/send
    round-trip are task 37 + frontend.
    """

    id: str          # stable token echoed back on selection, e.g. "slow"
    label: str       # user-facing text, e.g. "Slow — room to breathe"
    value: Any       # value written to the trip when this option is chosen


@dataclass(frozen=True)
class SlotRequest:
    """A single clarifying question (<= 200 chars per CLAUDE.md §7.1).

    If ``choices`` is set the client renders multiple-choice and the selected
    option's ``value`` maps deterministically to the trip write (zero
    extraction cost). If ``choices`` is None the slot is free-text.
    """

    slot: str
    prompt: str
    choices: Optional[list[ChoiceOption]] = None
    allow_multi: bool = False

    def to_wire(self) -> dict[str, Any]:
        """Serialize for the channel layer (web `metadata.ui` / Telegram keyboard).
        Task 43. `choices` is None for free-text slots."""
        return {
            "slot": self.slot,
            "prompt": self.prompt,
            "choices": (
                [{"id": c.id, "label": c.label, "value": c.value} for c in self.choices]
                if self.choices else None
            ),
            "allow_multi": self.allow_multi,
        }


@dataclass
class SideEffect:
    """A patch the dispatcher applies after the saga returns. One per logical
    write. ``kind`` selects the TripRepository method (see apply_side_effect)."""

    kind: str            # 'trip_patch' | 'destination_upsert' | 'booking_upsert' | ...
    payload: dict[str, Any]


@dataclass
class SagaResult:
    """What a saga returns. Only the owner saga sets ``text``."""

    text: Optional[str] = None
    slot_request: Optional[SlotRequest] = None
    state_delta: dict[str, Any] = field(default_factory=dict)
    side_effects: list[SideEffect] = field(default_factory=list)
    # passthrough for the orchestrator's existing token/cost logging
    _raw_response: Any = None
    _latency_ms: float = 0.0
    _search_responses: list[dict[str, Any]] = field(default_factory=list)


@runtime_checkable
class BaseSaga(Protocol):
    """Structural contract every saga satisfies. Not an ABC — sagas are plain
    classes; this Protocol documents the surface and powers isinstance checks
    in tests."""

    name: str

    def should_activate(
        self,
        intent: str,
        entities: dict[str, Any],
        trip: Optional[dict[str, Any]],
        state: SagaState,
    ) -> tuple[bool, bool]:
        """Return ``(can_act, wants_to_own_reply)``."""
        ...

    def run(
        self,
        message: str,
        user_doc: dict[str, Any],
        trip: Optional[dict[str, Any]],
        state: SagaState,
        conversation_context: str,
        events: Any,                 # EventEmitter (task 35)
    ) -> SagaResult:
        """Pure-ish: never mutates ``self``. Emits via ``events.emit(...)``."""
        ...
