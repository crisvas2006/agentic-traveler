"""PlanningSaga — the canonical slot-filling saga (Task 36).

Owns ``PLAN`` turns (and ``TRIP`` turns once a trip exists). On each turn it:
  1. extracts any planning facts present in the message (``slot_extractor``)
     and emits ``SideEffect``s that write them to the trip;
  2. derives the saga phase from the (locally updated) trip;
  3. either delegates to PlannerAgent (DETAILING / planning-ready ANCHORING),
     delegates to TripAgent for open exploration (DREAMING / SHAPING), or asks
     the single highest-priority missing slot — categorical slots as
     multiple-choice, free-form slots as text.

State-as-data: nothing is stored on ``self`` between turns.
"""

from __future__ import annotations

import copy
import logging
import time
from typing import Any, Optional

from agentic_traveler.core.observability import traceable
from agentic_traveler.orchestrator.client_factory import get_client
from agentic_traveler.orchestrator.planner_agent import PlannerAgent
from agentic_traveler.orchestrator.sagas.base import (
    ChoiceOption,
    SagaResult,
    SagaState,
    SideEffect,
    SlotRequest,
)
from agentic_traveler.orchestrator.sagas.saga_state import derive_saga_state_local
from agentic_traveler.orchestrator.sagas.slot_extractor import extract_trip_slots
from agentic_traveler.orchestrator.profile_utils import build_live_context
from agentic_traveler.orchestrator.trip_agent import TripAgent

logger = logging.getLogger(__name__)

_DEFAULT_CHAR_CAP = 1200

# Priority order in which missing slots are requested.
_SLOT_ORDER = ["destination", "timeframe", "travelers", "pace", "structure", "budget_tier"]

_SLOT_QUESTIONS = {
    "destination": "Where are you dreaming of going?",
    "timeframe": "Roughly when are you thinking?",
    "travelers": "Who's going — just you, a partner, friends, family?",
    "pace": "What pace feels right?",
    "structure": "How structured do you want it?",
    "budget_tier": "What's the budget vibe?",
}

# Categorical slots answered by selection (deterministic → no extraction cost).
_SLOT_CHOICES: dict[str, list[ChoiceOption]] = {
    "travelers": [
        ChoiceOption("solo", "Just me", "solo"),
        ChoiceOption("couple", "With my partner", "couple"),
        ChoiceOption("friends", "With friends", "friends"),
        ChoiceOption("family", "With family", "family"),
        ChoiceOption("skip", "Skip for now", "skip"),
    ],
    "pace": [
        ChoiceOption("slow", "Slow — room to breathe", "slow"),
        ChoiceOption("medium", "Medium — a good rhythm", "medium"),
        ChoiceOption("fast", "Fast — see a lot", "fast"),
        ChoiceOption("skip", "Skip for now", "skip"),
    ],
    "structure": [
        ChoiceOption("loose", "Loose, with a few anchors", "loose"),
        ChoiceOption("full", "A fuller day-by-day plan", "full"),
        ChoiceOption("skip", "Skip for now", "skip"),
    ],
    "budget_tier": [
        ChoiceOption("$", "$ — shoestring", "$"),
        ChoiceOption("$$", "$$ — comfortable", "$$"),
        ChoiceOption("$$$", "$$$ — treat yourself", "$$$"),
        ChoiceOption("$$$$", "$$$$ — no limits", "$$$$"),
        ChoiceOption("skip", "Skip for now", "skip"),
    ],
}

# Categorical slots whose chosen value writes straight into trip.preferences.
_PREFERENCE_SLOTS = ("pace", "structure", "budget_tier")

# Canonical set of values a categorical-slot button can send back. Used to
# intercept button taps the RouterAgent classifies as CHAT (the payload is a
# bare choice value like "slow" or "$$", not a travel question). Restricted to
# the preference slots: their values are unambiguous tokens, whereas travelers
# options ("friends", "family") are common words a real chat message might be.
_CHOICE_VALUES = frozenset(
    str(option.value).lower()
    for slot in _PREFERENCE_SLOTS
    for option in _SLOT_CHOICES[slot]
)

# Travelers is categorical too, but its chosen value writes into trip.travelers
# (not preferences). These presets give a count where it's unambiguous; friends/
# family leave count open (the user can refine it in free text later). The
# free-text extractor remains the fallback for typed answers.
_TRAVELER_PRESETS: dict[str, dict[str, Any]] = {
    "solo": {"count": 1, "composition": "solo"},
    "couple": {"count": 2, "composition": "couple"},
    "friends": {"composition": "friends"},
    "family": {"composition": "family"},
    "skip": {"composition": "skip"},
}

# Slots that accept more than one choice at once (e.g. "partner + family"). The
# client renders these as checkboxes + a Confirm button; "skip" stays exclusive.
_MULTI_SELECT_SLOTS = frozenset({"travelers"})

# The task-44 direction confirmation rides the same SlotRequest contract but is
# a "quick reply", not a deterministic write: its slot name is reserved and never
# maps to a trip field (see ``slot_selection_to_side_effect`` / ``ui_block_from_wire``).
_DIRECTION_SLOT = "trip_direction"


def _legal_values(slot: str) -> frozenset[str]:
    """Lower-cased set of values a categorical slot legally accepts (incl. 'skip')."""
    return frozenset(str(o.value).lower() for o in _SLOT_CHOICES.get(slot, []))


def ui_block_from_wire(wire: Optional[dict[str, Any]]) -> Optional[dict[str, Any]]:
    """Shape a ``SlotRequest.to_wire()`` dict into the channel-facing
    ``messages.metadata.ui`` block (Task 43), or ``None`` when there's nothing
    tappable (free-text slot / no slot question).

    The ``kind`` discriminator is a *rendering* decision made here, in the
    channel-shaping layer, so the frozen ``SlotRequest`` dataclass (§5) needs no
    new field:
      * a known categorical slot (anything in ``_SLOT_CHOICES``) → ``multi_choice``:
        tapping sends a structured ``selection`` and writes deterministically
        (no LLM).
      * anything else with choices (the direction confirmation) → ``quick_reply``:
        tapping sends ``send`` back as a NORMAL message (router re-classifies it).
    """
    if not wire or not wire.get("choices"):
        return None
    slot = wire["slot"]
    is_choice_slot = slot in _SLOT_CHOICES
    block: dict[str, Any] = {
        "kind": "multi_choice" if is_choice_slot else "quick_reply",
        "slot": slot,
        "prompt": wire["prompt"],
        "allow_multi": bool(wire.get("allow_multi")),
    }
    if is_choice_slot:
        # Deterministic slot: the client echoes the option id back as the value;
        # the backend re-validates it. The raw value never needs to leave here.
        block["options"] = [
            {"id": c["id"], "label": c["label"]} for c in wire["choices"]
        ]
    else:
        # Quick reply: the client sends `send` as a normal chat message.
        block["options"] = [
            {"id": c["id"], "label": c["label"], "send": c["value"]}
            for c in wire["choices"]
        ]
    if block["allow_multi"]:
        block["submit_label"] = "Confirm"
    return block


def slot_values_to_side_effect(
    trip: Optional[dict[str, Any]], slot: str, values: list[str]
) -> Optional[SideEffect]:
    """Map one or more tapped values for a categorical slot onto a single
    deterministic trip write (Task 43 — no LLM). Returns ``None`` when nothing
    legal was chosen, for a free-text slot, or when there's no trip.

    Multi-select (``travelers``) combines the chosen presets; single-select slots
    use the first legal value. ``'skip'`` is **exclusive**: if present it wins and
    clears the rest, writing a ``"skip"`` sentinel so key-presence marks the slot
    satisfied and the saga never re-asks it.

    Takes the hydrated ``trip`` (not just its id) because ``upsert_trip`` REPLACES
    the JSONB column — we merge into the existing section here so a selection
    never clobbers sibling keys."""
    trip_id = (trip or {}).get("id")
    if not trip_id:
        return None
    legal = _legal_values(slot)
    chosen: list[str] = []
    for v in values:
        n = str(v).strip().lower()
        if n in legal and n not in chosen:
            chosen.append(n)
    if not chosen:
        return None
    if "skip" in chosen:
        chosen = ["skip"]  # exclusive

    if slot in _PREFERENCE_SLOTS:
        # Single-select: take the first chosen value.
        merged = {**((trip or {}).get("preferences") or {}), slot: chosen[0]}
        return SideEffect(kind="trip_patch", payload={"id": trip_id, "preferences": merged})

    if slot == "travelers":
        merged = dict((trip or {}).get("travelers") or {})
        if chosen == ["skip"]:
            merged["composition"] = "skip"
            merged.pop("count", None)
        else:
            merged["composition"] = ", ".join(
                _TRAVELER_PRESETS[c]["composition"] for c in chosen
            )
            # A count only when a single, unambiguous preset was picked.
            if len(chosen) == 1 and "count" in _TRAVELER_PRESETS[chosen[0]]:
                merged["count"] = _TRAVELER_PRESETS[chosen[0]]["count"]
            else:
                merged.pop("count", None)
        return SideEffect(kind="trip_patch", payload={"id": trip_id, "travelers": merged})

    return None


def slot_selection_to_side_effect(
    trip: Optional[dict[str, Any]], slot: str, value: str
) -> Optional[SideEffect]:
    """Single-value convenience wrapper around :func:`slot_values_to_side_effect`."""
    return slot_values_to_side_effect(trip, slot, [value])


class PlanningSaga:
    """Owns the trip-planning conversation."""

    name = "PlanningSaga"

    def __init__(self, client: Any = None):
        self._client = client or get_client()
        self._planner = PlannerAgent(client=self._client)
        self._trip_agent = TripAgent(client=self._client)

    def should_activate(
        self,
        intent: str,
        entities: dict[str, Any],
        trip: Optional[dict[str, Any]],
        state: SagaState,
    ) -> tuple[bool, bool]:
        if intent == "PLAN":
            return True, True
        if intent == "TRIP" and trip is not None:
            return True, True
        if intent == "CHAT" and trip is not None:
            # Intercept categorical-slot button taps the RouterAgent classifies
            # as CHAT (the payload is a bare choice value, e.g. "slow" or "$$",
            # not a travel question). Vocab is derived from _SLOT_CHOICES.
            msg = state.get("message_text", "").strip().lower()
            if msg in _CHOICE_VALUES:
                return True, True
        return False, False

    @traceable(name="saga.planning.run")
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

        overrides = _hard_overrides(user_doc)

        # 1. Extract any facts in this message and stage writes.
        side_effects: list[SideEffect] = []
        extracted: dict[str, Any] = {}
        try:
            pending_slot = state.get("pending_slot")
            extracted = extract_trip_slots(self._client, message, pending_slot=pending_slot)
            if extracted:
                events.emit("metric", {
                    "name": "slot_filled", "saga": self.name,
                    "slots": sorted(extracted.keys()),
                })
            side_effects = _slots_to_side_effects(extracted, trip)
            trip = _apply_local(trip, extracted)
        except Exception:
            logger.warning("PlanningSaga slot extraction failed.", exc_info=True)

        return self._decide(
            message, user_doc, trip, state, conversation_context, events,
            side_effects=side_effects, made_progress=bool(side_effects),
            overrides=overrides, t=t,
        )

    @traceable(name="saga.planning.run_after_selection")
    def run_after_selection(
        self,
        message: str,
        user_doc: dict[str, Any],
        trip: Optional[dict[str, Any]],
        state: SagaState,
        conversation_context: str,
        events: Any,
    ) -> SagaResult:
        """Continue a planning turn after a deterministic choice was tapped
        (Task 43). The chosen value has ALREADY been written to ``trip`` (and
        persisted) by the orchestrator's selection entrypoint, so we skip
        extraction entirely — no LLM call — and just decide the next step.

        ``made_progress=True`` because the tap is real progress: a now-complete
        trip proceeds to the itinerary, an incomplete one asks the next missing
        slot (never drifts to the companion)."""
        t = time.time()
        events.emit("metric", {"name": "saga_entered", "saga": self.name})
        overrides = _hard_overrides(user_doc)
        return self._decide(
            message, user_doc, trip, state, conversation_context, events,
            side_effects=[], made_progress=True, overrides=overrides, t=t,
        )

    def _decide(
        self,
        message: str,
        user_doc: dict[str, Any],
        trip: Optional[dict[str, Any]],
        state: SagaState,
        conversation_context: str,
        events: Any,
        *,
        side_effects: list[SideEffect],
        made_progress: bool,
        overrides: dict[str, Any],
        t: float,
    ) -> SagaResult:
        """Route a planning turn once the trip reflects any writes staged this
        turn. Shared by ``run`` (after extraction) and ``run_after_selection``
        (deterministic tap, no extraction)."""
        # Task 41 AC-4: fold the latest mood check-in into the context so the
        # content engines (TripAgent / PlannerAgent) adapt pacing and swaps.
        conversation_context = conversation_context + build_live_context(trip)
        phase = derive_saga_state_local(trip)
        missing = self._first_missing_slot(trip, overrides)
        intent = state.get("intent", "")
        directive = state.get("trip_directive", "unspecified")
        superseded = state.get("superseded_trip_title")

        def _focus(outcome: str) -> None:
            events.emit("metric", {
                "name": "trip_focus_resolved", "directive": directive,
                "outcome": outcome,
            })

        # In-trip / post-trip: hand to the companion content engine, never
        # slot-fill a trip that is already underway or finished.
        if phase in ("LIVING", "REMEMBERING"):
            _focus("companion")
            return self._delegate(
                self._trip_agent, "TripAgent", user_doc, message,
                conversation_context, state, side_effects, events, t,
            )

        # Still collecting essentials.
        if missing is not None:
            # Let the user drift. If they're asking a question or exploring
            # (intent TRIP) rather than answering the open slot, ANSWER them via
            # the content engine instead of re-asking the slot. Any planning
            # facts they mentioned were still captured above as side_effects.
            # Without this guard the saga gets stuck re-asking the last missing
            # slot (e.g. "What's the budget vibe?") no matter what the user says.
            if intent == "TRIP" and not made_progress:
                _focus("companion")
                return self._delegate(
                    self._trip_agent, "TripAgent", user_doc, message,
                    conversation_context, state, side_effects, events, t,
                )
            # Otherwise collect the essentials one question at a time (AC-3/AC-9).
            # On a fresh trip that just superseded another, acknowledge the trip
            # set aside on the first prompt (task 44 AC-4).
            _focus("new_trip" if superseded else "slot_fill")
            return self._ask_slot(
                missing, side_effects, events, t,
                superseded=superseded if missing == "destination" else None,
            )

        # ── All essentials known. ────────────────────────────────────────────
        # Direction check (task 44): a generic plan-start ("I want to plan a
        # trip") on a COMPLETE trip is ambiguous — regenerate this one, or start
        # a new one? Confirm rather than silently rebuilding the wrong trip. (A
        # complete trip always has a destination, so it's genuinely established.)
        if intent == "PLAN" and directive == "unspecified" and not made_progress:
            _focus("confirm_switch")
            return self._confirm_switch(trip, events, t)

        # The heavy itinerary builder runs ONLY when the user is actually
        # continuing/refining — an explicit "continue" directive, or a turn where
        # they supplied a new planning fact worth re-planning around. A complete
        # trip plus a casual message (a weather check, idle chat) is NOT a reason
        # to regenerate the itinerary: the user drifts to the lighter companion.
        # The trip stays in focus, but the user's message dictates the engine.
        if directive == "continue" or made_progress:
            _focus("plan")
            return self._delegate(
                self._planner, "PlannerAgent", user_doc, message,
                conversation_context, state, side_effects, events, t,
            )
        _focus("companion")
        return self._delegate(
            self._trip_agent, "TripAgent", user_doc, message,
            conversation_context, state, side_effects, events, t,
        )

    # ------------------------------------------------------------------
    # slot logic
    # ------------------------------------------------------------------

    def _first_missing_slot(
        self, trip: Optional[dict[str, Any]], overrides: dict[str, Any]
    ) -> Optional[str]:
        if trip is None:
            return "destination"
        filled = _slot_values(trip)
        for slot in _SLOT_ORDER:
            if slot in overrides:
                continue
            if not filled.get(slot):
                return slot
        return None

    def _ask_slot(
        self, slot: str, side_effects: list[SideEffect], events: Any, t: float,
        superseded: Optional[str] = None,
    ) -> SagaResult:
        question = _SLOT_QUESTIONS[slot]
        choices = _SLOT_CHOICES.get(slot)
        # When a fresh trip just set another aside, acknowledge it on the first
        # prompt so the switch feels deliberate (task 44 AC-4).
        text = question
        if superseded:
            text = f"Putting {_clip_title(superseded)} on hold — let's start fresh. {question}"
        events.emit("metric", {"name": "slot_request_emitted", "slot": slot})
        events.emit("metric", {
            "name": "saga_exited", "saga": self.name, "outcome": "slot_request",
            "latency_ms": (time.time() - t) * 1000,
        })
        return SagaResult(
            text=text,
            slot_request=SlotRequest(
                slot=slot, prompt=question, choices=choices,
                allow_multi=slot in _MULTI_SELECT_SLOTS,
            ),
            side_effects=side_effects,
            state_delta={"pending_slot": slot},
        )

    def _confirm_switch(self, trip: dict[str, Any], events: Any, t: float) -> SagaResult:
        """Ask the user whether to keep refining the in-focus trip or start a new
        one (task 44). No plan, no slot mutation. The reply next turn
        (router → continue/new) decides; nothing is persisted.

        Carries a ``quick_reply`` SlotRequest (task 43) so channels can render
        two tappable chips. Unlike a categorical slot, these don't write to the
        trip: each chip's ``value`` is a short phrase sent back as a NORMAL
        message, which the router re-classifies into a ``trip_directive`` —
        keeping the confirmation stateless (no persisted "awaiting" flag)."""
        title = _trip_title(trip)
        text = (
            f"We're partway through planning {title}. Want to keep refining "
            f"that, or start a brand-new trip?"
        )
        events.emit("metric", {
            "name": "saga_exited", "saga": self.name, "outcome": "confirm_switch",
            "latency_ms": (time.time() - t) * 1000,
        })
        return SagaResult(
            text=text,
            slot_request=SlotRequest(
                slot=_DIRECTION_SLOT,
                prompt=text,
                choices=[
                    ChoiceOption("continue", "Keep refining this trip",
                                 "Let's keep refining this trip."),
                    ChoiceOption("new", "Start a new trip",
                                 "Let's start planning a brand-new trip."),
                ],
            ),
        )

    # ------------------------------------------------------------------
    # delegation to content engines
    # ------------------------------------------------------------------

    def _delegate(
        self,
        agent: Any,
        agent_label: str,
        user_doc: dict[str, Any],
        message: str,
        conversation_context: str,
        state: SagaState,
        side_effects: list[SideEffect],
        events: Any,
        t: float,
    ) -> SagaResult:
        try:
            result = agent.process_request(
                user_doc=user_doc,
                message=message,
                conversation_context=conversation_context,
                current_time=state.get("current_time", ""),
                preference_raw=state.get("preference_raw"),
                events=events,
            )
        except Exception:
            logger.exception("PlanningSaga delegate to %s failed.", agent_label)
            events.emit("metric", {"name": "error_raised", "saga": self.name})
            events.emit("metric", {
                "name": "saga_exited", "saga": self.name, "outcome": "error",
                "latency_ms": (time.time() - t) * 1000,
            })
            return SagaResult(
                text="Sorry, something glitched on my end. Mind trying that again?",
                side_effects=side_effects,
            )

        text = result.get("text", "")
        events.emit("metric", {
            "name": "saga_exited", "saga": self.name, "outcome": agent_label,
            "latency_ms": (time.time() - t) * 1000,
        })
        return SagaResult(
            text=text,
            side_effects=side_effects,
            _raw_response=result.get("_raw_response"),
            _latency_ms=result.get("_latency_ms", 0.0),
            _search_responses=result.get("_search_responses", []) or [],
        )


# ---------------------------------------------------------------------------
# module-level helpers (pure functions — easy to unit test)
# ---------------------------------------------------------------------------

def _clip_title(title: str, cap: int = 60) -> str:
    title = (title or "").strip()
    return title if len(title) <= cap else title[: cap - 1].rstrip() + "…"


def _trip_title(trip: Optional[dict[str, Any]]) -> str:
    """A short, human label for the in-focus trip: its title, else its first
    destination, else a generic fallback. Used in confirmation/ack text."""
    if not trip:
        return "your current trip"
    title = (trip.get("title") or "").strip()
    if title:
        # Strip a trailing generic word so "Japan trip" reads as "Japan".
        head = title.split(",")[0].strip()
        return _clip_title(head or title)
    dests = trip.get("destinations") or []
    for d in dests:
        name = (d.get("name") or "").strip()
        if name:
            return _clip_title(f"your {name} trip")
    return "your current trip"


def _slot_values(trip: dict[str, Any]) -> dict[str, Any]:
    """Which slots are satisfied. ``destination`` counts as filled when ANY
    destination exists (considering or confirmed) — see task 36 §4.1 note."""
    prefs = trip.get("preferences") or {}
    travelers = trip.get("travelers") or {}
    timeframe = (trip.get("discovery") or {}).get("timeframe") or {}
    destinations = trip.get("destinations") or []
    return {
        "destination": bool(destinations),
        "timeframe": bool(timeframe.get("start_date") or timeframe.get("text")),
        # A tapped travelers choice may set only ``composition`` (friends/family,
        # no exact count) — presence of either marks the slot satisfied.
        "travelers": bool(travelers.get("count") or travelers.get("composition")),
        "pace": "pace" in prefs,
        "structure": "structure" in prefs,
        "budget_tier": "budget_tier" in prefs,
    }


def _hard_overrides(user_doc: dict[str, Any]) -> dict[str, Any]:
    """Return ``{slot: value}`` from ``profile_data.hard_overrides`` (CLAUDE §7.1)."""
    profile_data = (user_doc.get("user_profile") or {}).get("profile_data") or {}
    overrides = profile_data.get("hard_overrides") or []
    out: dict[str, Any] = {}
    for o in overrides:
        if not isinstance(o, dict):
            continue
        slot = (o.get("slot") or "").removeprefix("ask.")
        if slot:
            out[slot] = o.get("value")
    return out


def _slots_to_side_effects(
    extracted: dict[str, Any], trip: Optional[dict[str, Any]]
) -> list[SideEffect]:
    """Turn extracted facts into trip writes, merging into existing JSONB so we
    never clobber sibling keys."""
    if not extracted or trip is None:
        return []
    trip_id = trip.get("id")
    if not trip_id:
        return []

    effects: list[SideEffect] = []

    # Destinations → child rows (status 'considering').
    existing_names = {
        (d.get("name") or "").strip().lower() for d in (trip.get("destinations") or [])
    }
    for name in extracted.get("destinations", []):
        if name.strip().lower() in existing_names:
            continue
        effects.append(SideEffect(
            kind="destination_upsert",
            payload={"trip_id": trip_id, "name": name, "status": "considering"},
        ))

    # JSONB section merges, batched into a single trip_patch.
    patch: dict[str, Any] = {}
    if "timeframe" in extracted:
        discovery = dict(trip.get("discovery") or {})
        discovery["timeframe"] = {**(discovery.get("timeframe") or {}), **extracted["timeframe"]}
        patch["discovery"] = discovery
    if "travelers" in extracted:
        patch["travelers"] = {**(trip.get("travelers") or {}), **extracted["travelers"]}
    prefs_update = {
        k: extracted[k] for k in ("pace", "structure", "budget_tier") if k in extracted
    }
    if prefs_update:
        patch["preferences"] = {**(trip.get("preferences") or {}), **prefs_update}
    if patch:
        patch["id"] = trip_id
        effects.append(SideEffect(kind="trip_patch", payload=patch))

    return effects


def _apply_local(
    trip: Optional[dict[str, Any]], extracted: dict[str, Any]
) -> Optional[dict[str, Any]]:
    """Return a copy of ``trip`` with ``extracted`` merged in, so the missing-slot
    computation reflects writes staged this turn."""
    if trip is None or not extracted:
        return trip
    local = copy.deepcopy(trip)
    for name in extracted.get("destinations", []):
        local.setdefault("destinations", []).append(
            {"name": name, "status": "considering"}
        )
    if "timeframe" in extracted:
        discovery = local.setdefault("discovery", {})
        discovery["timeframe"] = {**(discovery.get("timeframe") or {}), **extracted["timeframe"]}
    if "travelers" in extracted:
        local["travelers"] = {**(local.get("travelers") or {}), **extracted["travelers"]}
    for key in ("pace", "structure", "budget_tier"):
        if key in extracted:
            local.setdefault("preferences", {})[key] = extracted[key]
    return local
