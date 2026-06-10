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
import re
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
from agentic_traveler.orchestrator.curiosity_injector import (
    frame_curiosity_prompt,
    get_injector,
    is_today_iso,
    today_iso,
)
from agentic_traveler.orchestrator.profile_utils import (
    build_live_context,
    build_profile_summary,
)
from agentic_traveler.orchestrator.sagas.advisor_turn import compose_advisor_turn
from agentic_traveler.orchestrator.sagas.destination_brief import ensure_brief
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
    choices = wire["choices"]
    is_choice_slot = slot in _SLOT_CHOICES
    # Task 45: an advisory proposal carries a "confirm" option whose value is the
    # proposed value — the structural discriminator for the `proposal` kind. The
    # confirm tap sends a deterministic `selection {slot, [value]}` (validated
    # server-side against the persisted pending proposal); other/skip send a
    # plain message that re-engages the composer / skip path.
    is_proposal = not is_choice_slot and any(c["id"] == "confirm" for c in choices)
    if is_proposal:
        return {
            "kind": "proposal",
            "slot": slot,
            "prompt": wire["prompt"],
            "allow_multi": False,
            "options": [
                {"id": c["id"], "label": c["label"],
                 **({"value": c["value"]} if c["id"] == "confirm" else {"send": c["value"]})}
                for c in choices
            ],
        }
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
            {"id": c["id"], "label": c["label"]} for c in choices
        ]
    else:
        # Quick reply: the client sends `send` as a normal chat message.
        block["options"] = [
            {"id": c["id"], "label": c["label"], "send": c["value"]}
            for c in choices
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


def proposal_selection_to_side_effect(
    trip: Optional[dict[str, Any]], slot: str, value: str
) -> Optional[SideEffect]:
    """Task 45: a tapped advisory proposal / suggestion is valid ONLY if its
    ``(slot, value)`` matches the trip's persisted ``pending_proposal`` (or a
    pending suggestion) — trust-but-verify. Returns the deterministic write, or
    ``None`` on a mismatch (stale / tampered tap)."""
    advisor = _advisor_state(trip)
    pending = advisor.get("pending_proposal") or {}
    if pending.get("slot") == slot and str(pending.get("value")) == str(value):
        return _proposal_write(trip, pending)
    if slot == "destination":
        for sug in advisor.get("pending_suggestions") or []:
            if str(sug.get("value")) == str(value):
                return _proposal_write(
                    trip, {"slot": "destination", "value": value, "label": sug.get("label")}
                )
    return None


# ── Task 45 — advisory turns (insight-led slot filling) ──────────────────────
# Only `timeframe` is advisory in the PlanningSaga: destination has a brief by
# the time timeframe is open, so the composer can ground its insight.
# Destination *discovery* (no destination yet) is the DiscoverySaga's job.
_ADVISORY_SLOTS = ("timeframe",)
_ADVISOR_SLOT_CAP = 350

_AFFIRMATIONS = frozenset({
    "yes", "y", "yep", "yeah", "ok", "okay", "sure", "sounds good", "sounds great",
    "perfect", "do it", "let's do it", "lets do it", "great", "go for it", "set it",
    "yes please", "please do", "that works", "works for me",
})
_INTERROGATIVE_CUES = (
    "what about", "how about", "what if", "would ", "could ", "should i",
    "is it", "are there", "what's the", "whats the", "when is", "when's",
)


def _is_affirmation(message: str) -> bool:
    return (message or "").strip().lower().rstrip("!. ") in _AFFIRMATIONS


def _is_interrogative(message: str) -> bool:
    m = (message or "").lower()
    return "?" in m or any(cue in m for cue in _INTERROGATIVE_CUES)


def _advisor_state(trip: Optional[dict[str, Any]]) -> dict[str, Any]:
    return dict(((trip or {}).get("discovery") or {}).get("advisor") or {})


def _discovery_patch(trip: Optional[dict[str, Any]], **changes: Any) -> SideEffect:
    """A trip_patch carrying the trip's discovery dict with ``changes`` merged in
    (the column is replaced wholesale on write, so we merge here). A ``None``
    value deletes that key — used to clear ``advisor`` pending state."""
    disc = dict((trip or {}).get("discovery") or {})
    for key, val in changes.items():
        if val is None:
            disc.pop(key, None)
        else:
            disc[key] = val
    return SideEffect(kind="trip_patch", payload={"id": (trip or {}).get("id"), "discovery": disc})


def _set_pending_proposal(
    trip: Optional[dict[str, Any]], proposal: Optional[dict[str, Any]]
) -> SideEffect:
    """Persist (or clear) ``discovery.advisor.pending_proposal`` on the trip."""
    advisor = _advisor_state(trip)
    if proposal:
        advisor["pending_proposal"] = proposal
    else:
        advisor.pop("pending_proposal", None)
    return _discovery_patch(trip, advisor=advisor or None)


def _proposal_write(
    trip: Optional[dict[str, Any]], proposal: dict[str, Any]
) -> Optional[SideEffect]:
    """Map a CONFIRMED proposal (slot+value) onto a trip write, also clearing the
    pending proposal. Currently timeframe (→ discovery.timeframe) and destination
    (→ confirmed child row)."""
    slot, value = proposal.get("slot"), proposal.get("value")
    trip_id = (trip or {}).get("id")
    if not (slot and value and trip_id):
        return None
    if slot == "timeframe":
        tf = dict(((trip or {}).get("discovery") or {}).get("timeframe") or {})
        tf["text"] = proposal.get("label") or value
        if re.fullmatch(r"\d{4}-\d{2}", str(value)):
            tf["start_date"] = f"{value}-01"
        elif re.fullmatch(r"\d{4}-\d{2}-\d{2}", str(value)):
            tf["start_date"] = str(value)
        advisor = _advisor_state(trip)
        advisor.pop("pending_proposal", None)
        return _discovery_patch(trip, timeframe=tf, advisor=advisor or None)
    if slot == "destination":
        return SideEffect(
            kind="destination_upsert",
            payload={"trip_id": trip_id, "name": str(value), "status": "confirmed"},
        )
    return None


def _coalesce_trip_patches(side_effects: list[SideEffect]) -> list[SideEffect]:
    """Merge all ``trip_patch`` side effects in a turn into ONE, deep-merging
    JSONB section dicts. ``upsert_trip`` replaces each column wholesale, so two
    discovery patches in a turn would otherwise clobber each other (e.g. a brief
    capture + a timeframe write)."""
    merged: dict[str, Any] = {}
    out: list[SideEffect] = []
    patch_index: Optional[int] = None
    for se in side_effects:
        if getattr(se, "kind", None) != "trip_patch":
            out.append(se)
            continue
        for key, val in (se.payload or {}).items():
            if isinstance(val, dict) and isinstance(merged.get(key), dict):
                merged[key] = {**merged[key], **val}
            else:
                merged[key] = val
        if patch_index is None:
            patch_index = len(out)
            out.append(SideEffect(kind="trip_patch", payload=merged))
    if patch_index is not None:
        out[patch_index] = SideEffect(kind="trip_patch", payload=merged)
    return out


def _apply_side_effect_local(
    trip: Optional[dict[str, Any]], se: SideEffect
) -> Optional[dict[str, Any]]:
    """Reflect a staged SideEffect onto a local copy of the trip so the
    missing-slot computation this turn sees it (mirrors ``_apply_local``)."""
    if trip is None:
        return trip
    local = copy.deepcopy(trip)
    if se.kind == "trip_patch":
        for key, val in (se.payload or {}).items():
            if key != "id":
                local[key] = val
    elif se.kind == "destination_upsert":
        local.setdefault("destinations", []).append(
            {"name": se.payload.get("name"), "status": se.payload.get("status", "considering")}
        )
    return local


def _dna_default_line(slot: str, user_doc: dict[str, Any]) -> str:
    """A zero-LLM personalization prefix for a chip slot, from stored profile
    signal. "" when there's no usable signal (AC-9)."""
    pd = (user_doc.get("user_profile") or {}).get("profile_data") or {}
    prefs = pd.get("trip_defaults") or pd.get("last_trip_preferences") or {}
    val = prefs.get(slot)
    labels = {
        "pace": {"slow": "ran slow", "medium": "kept a steady rhythm", "fast": "moved fast"},
        "structure": {"loose": "stayed loose", "full": "were fully planned"},
    }
    phrase = (labels.get(slot) or {}).get(str(val).lower()) if val else None
    if phrase:
        return f"Your last trips {phrase} — same again? "
    return ""


def _state_signal(trip: Optional[dict[str, Any]]) -> Optional[str]:
    """Short current-state line for the composer (STATE OVER TRAIT), from the
    latest mood check-in (task 41). None when no mood is logged."""
    lm = ((trip or {}).get("live_state") or {}).get("last_mood") or {}
    label = lm.get("label")
    return f"feeling {label}" if label else None


def _proposal_slot_request(slot: str, prompt: str, proposal: dict[str, Any]) -> SlotRequest:
    """A proposal SlotRequest: [Set <label>] [Another time] [Skip for now]. The
    ``confirm`` option id is the structural discriminator the channel layer uses
    to render kind ``proposal`` (the SlotRequest dataclass stays frozen)."""
    return SlotRequest(
        slot=slot, prompt=prompt,
        choices=[
            ChoiceOption("confirm", f"Set {proposal.get('label')}", str(proposal.get("value"))),
            ChoiceOption("other", "Another time", "another time"),
            ChoiceOption("skip", "Skip for now", "skip"),
        ],
        allow_multi=False,
    )


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
        side_effects: list[SideEffect] = []
        made_progress = False

        # 0. Task 45 — resolve a pending advisory proposal BEFORE extraction.
        pending = _advisor_state(trip).get("pending_proposal")
        suppress_extraction = False
        if pending:
            if _is_affirmation(message):
                se = _proposal_write(trip, pending)
                if se is not None:
                    side_effects.append(se)
                    trip = _apply_side_effect_local(trip, se)
                    made_progress = True
                    events.emit("metric", {"name": "proposal_accepted", "slot": pending.get("slot")})
            elif _is_interrogative(message):
                # Counter-proposal ("what about May?") — clear the pending
                # proposal, write nothing, and let the composer re-propose.
                clear = _set_pending_proposal(trip, None)
                side_effects.append(clear)
                trip = _apply_side_effect_local(trip, clear)
                suppress_extraction = True
                events.emit("metric", {"name": "proposal_rejected", "slot": pending.get("slot")})
            # else: ambiguous → fall through; a decisive restatement still
            # writes via the extractor (AC-6).

        # 1. Extract any facts in this message and stage writes (unless we're in
        #    a counter-proposal loop, where the composer re-proposes instead).
        if not suppress_extraction:
            try:
                pending_slot = state.get("pending_slot")
                extracted = extract_trip_slots(self._client, message, pending_slot=pending_slot)
                # AC-1/AC-6: when the message is a QUESTION about a knowledge slot
                # ("september, what's the best time?"), don't let the bare value
                # short-circuit the advisory turn — drop it so the composer
                # answers and PROPOSES it (confirm-to-write). A decisive statement
                # ("September, that's fixed") is non-interrogative → writes here.
                if extracted and _is_interrogative(message):
                    extracted.pop("timeframe", None)
                if extracted:
                    events.emit("metric", {
                        "name": "slot_filled", "saga": self.name,
                        "slots": sorted(extracted.keys()),
                    })
                side_effects.extend(_slots_to_side_effects(extracted, trip))
                trip = _apply_local(trip, extracted)
                made_progress = made_progress or bool(extracted)
            except Exception:
                logger.warning("PlanningSaga slot extraction failed.", exc_info=True)

        # 2. Capture the destination brief once a destination exists (AC-2).
        try:
            brief_se = ensure_brief(self._client, trip, user_doc, events)
            if brief_se is not None:
                side_effects.append(brief_se)
                trip = _apply_side_effect_local(trip, brief_se)
        except Exception:
            logger.warning("ensure_brief failed.", exc_info=True)

        result = self._decide(
            message, user_doc, trip, state, conversation_context, events,
            side_effects=side_effects, made_progress=made_progress,
            overrides=overrides, t=t,
        )
        result.side_effects = _coalesce_trip_patches(result.side_effects)
        return result

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
        result = self._decide(
            message, user_doc, trip, state, conversation_context, events,
            side_effects=[], made_progress=True, overrides=overrides, t=t,
        )
        result.side_effects = _coalesce_trip_patches(result.side_effects)
        return result

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
                conversation_context + self._curiosity_suffix(trip, user_doc, phase, side_effects, events),
                state, side_effects, events, t,
            )

        # Still collecting essentials.
        if missing is not None:
            interrogative = _is_interrogative(message)

            # Task 45: a knowledge slot (timeframe) becomes an advisory turn —
            # the composer answers any question AND proposes a value in one reply.
            if missing in _ADVISORY_SLOTS and missing not in overrides:
                advised = self._advise_slot(
                    missing, message, trip, user_doc, state,
                    conversation_context, side_effects, events, t,
                )
                if advised is not None:
                    _focus("advise_slot")
                    return advised
                # composer failed → fall through to the static question (AC-10).

            # Task 45 / AC-11 (the "September bug"): a question asked while a CHIP
            # slot is open is ANSWERED, and the open slot is re-attached to the
            # SAME reply — never dropped. (Knowledge slots that reach here had a
            # composer failure → fall through to the static question, AC-10.)
            if interrogative and missing not in _ADVISORY_SLOTS:
                _focus("answer_and_reask")
                return self._answer_and_reask(
                    missing, message, user_doc, trip, conversation_context,
                    state, side_effects, events, t,
                )

            # Open drift: exploring (intent TRIP) without progress → companion
            # answers rather than the saga re-asking the same slot.
            if intent == "TRIP" and not made_progress:
                _focus("companion")
                return self._delegate(
                    self._trip_agent, "TripAgent", user_doc, message,
                    conversation_context + self._curiosity_suffix(trip, user_doc, phase, side_effects, events),
                    state, side_effects, events, t,
                )
            # Otherwise collect the essentials one question at a time (AC-3/AC-9).
            _focus("new_trip" if superseded else "slot_fill")
            return self._ask_slot(
                missing, side_effects, events, t, user_doc=user_doc,
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
            conversation_context + self._curiosity_suffix(trip, user_doc, phase, side_effects, events),
            state, side_effects, events, t,
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
        superseded: Optional[str] = None, user_doc: Optional[dict[str, Any]] = None,
    ) -> SagaResult:
        question = _SLOT_QUESTIONS[slot]
        choices = _SLOT_CHOICES.get(slot)
        # Task 45 AC-9: a zero-LLM DNA-default prefix when the profile has signal
        # ("Your last trips ran slow — same again?"). The chip card shows the
        # plain question; the spoken text leads with the personalization.
        dna_prefix = _dna_default_line(slot, user_doc or {})
        # When a fresh trip just set another aside, acknowledge it on the first
        # prompt so the switch feels deliberate (task 44 AC-4).
        text = dna_prefix + question
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
    # advisory turns (task 45)
    # ------------------------------------------------------------------

    def _advise_slot(
        self, slot: str, message: str, trip: Optional[dict[str, Any]],
        user_doc: dict[str, Any], state: SagaState, conversation_context: str,
        side_effects: list[SideEffect], events: Any, t: float,
    ) -> Optional[SagaResult]:
        """Compose an advisory turn for a knowledge slot: answer any question,
        offer one grounded insight, propose a value with confirm chips. Returns
        ``None`` on composer failure so the caller falls back to the static
        question (AC-10)."""
        brief = ((trip or {}).get("discovery") or {}).get("destination_brief")
        dna = build_profile_summary(user_doc or {}, include_scores=False)
        c0 = time.time()
        turn = compose_advisor_turn(
            self._client, mode="advise_slot", slot=slot, message=message,
            brief=brief, dna_summary=dna, state_signal=_state_signal(trip),
            curiosity_prompt=None, conversation_context=conversation_context,
            char_cap=_ADVISOR_SLOT_CAP,
        )
        if turn is None:
            return None
        events.emit("metric", {
            "name": "advisor_turn_composed", "mode": "advise_slot",
            "latency_ms": int((time.time() - c0) * 1000),
        })
        if turn.truncated:
            events.emit("metric", {"name": "advisor_budget_overflow", "slot": slot})

        slot_request = None
        if turn.proposal:
            side_effects.append(_set_pending_proposal(trip, turn.proposal))
            events.emit("metric", {"name": "proposal_made", "slot": slot})
            slot_request = _proposal_slot_request(slot, turn.text, turn.proposal)
        events.emit("metric", {
            "name": "saga_exited", "saga": self.name, "outcome": "advise_slot",
            "latency_ms": (time.time() - t) * 1000,
        })
        return SagaResult(
            text=turn.text, slot_request=slot_request, side_effects=side_effects,
            state_delta={"pending_slot": slot},
        )

    def _answer_and_reask(
        self, slot: str, message: str, user_doc: dict[str, Any],
        trip: Optional[dict[str, Any]], conversation_context: str,
        state: SagaState, side_effects: list[SideEffect], events: Any, t: float,
    ) -> SagaResult:
        """AC-11 / the "September bug": answer the user's question via the
        companion AND re-attach the open chip slot to the SAME reply, so the
        question is never dropped and the flow still advances."""
        phase = derive_saga_state_local(trip)
        result = self._delegate(
            self._trip_agent, "TripAgent", user_doc, message,
            conversation_context + self._curiosity_suffix(trip, user_doc, phase, side_effects, events),
            state, side_effects, events, t,
        )
        result.slot_request = SlotRequest(
            slot=slot, prompt=_SLOT_QUESTIONS[slot], choices=_SLOT_CHOICES.get(slot),
            allow_multi=slot in _MULTI_SELECT_SLOTS,
        )
        return result

    # ------------------------------------------------------------------
    # delegation to content engines
    # ------------------------------------------------------------------

    def _curiosity_suffix(
        self,
        trip: Optional[dict[str, Any]],
        user_doc: dict[str, Any],
        phase: str,
        side_effects: list[SideEffect],
        events: Any,
    ) -> str:
        """Task 42: pick at most one curiosity prompt for an exploratory /
        reflective companion turn and return its framed (optional-aside) text to
        append to the context. Once per day per trip (a ``scratchpad`` marker),
        and only on companion turns — never on a slot question. Returns "" when
        nothing should be injected. Called only on the taken companion branch,
        so it runs at most once per turn."""
        if phase not in ("DREAMING", "SHAPING", "REMEMBERING"):
            return ""
        scratch = (trip or {}).get("scratchpad") or {}
        session_state = {
            "curiosity_used_this_session": is_today_iso(scratch.get("curiosity_last_at")),
        }
        try:
            prompt = get_injector().select(phase, user_doc, session_state, trip=trip)
        except Exception:
            logger.warning("curiosity injector failed; skipping.", exc_info=True)
            return ""
        if not prompt:
            return ""
        events.emit("metric", {
            "name": "curiosity_prompt_injected", "id": prompt.id, "saga": self.name,
        })
        side_effects.append(SideEffect(
            kind="trip_patch",
            payload={"id": (trip or {}).get("id"), "scratchpad": {**scratch, "curiosity_last_at": today_iso()}},
        ))
        return frame_curiosity_prompt(prompt.text)

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
