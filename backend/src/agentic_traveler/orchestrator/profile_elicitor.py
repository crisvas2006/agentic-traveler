"""Task 55 — just-in-time Traveler-DNA elicitation (adapted for erratic users).

A deterministic, no-LLM selector (the twin of ``CuriosityPromptInjector``) that
weaves ONE tappable Traveler-DNA question into an already-useful reply — plus the
handling for how real people actually behave: they ignore it, deviate, skip one, or
say "stop asking". The user is NEVER blocked.

Skip model (adapted from the original spec's permanent sentinel):
  - Skips are SOFT and scoped to the **current flow run** — re-askable in a future
    run. A question is offered at most once per run (tracked in ``asked``); ignoring
    it or saying "skip this" simply moves on to the next.
  - "go on without questions" / "no more questions" **mutes** the rest of the run.
  - A permanent "never ask me X" stays the existing ``hard_overrides`` path.

State-as-data: per-run state lives on the trip (``trip.live_state.elicitation``) so
it survives across turns but resets naturally for a new trip/run:

    {
      "asked": ["trip_intent_this_time", ...],   # offered this run (never re-offered)
      "answered_flow": {"energy_for_this_trip": "high"},  # flow_state answers this run
      "muted": false,                            # user said "stop" → no more this run
      "pending": "trip_intent_this_time" | null  # qid offered last turn (to read a typed reply)
    }
"""

from __future__ import annotations

import os
from typing import Any, Optional

from agentic_traveler.orchestrator.profile_coverage import compute_gap
from agentic_traveler.orchestrator.profile_questions import BY_ID
from agentic_traveler.orchestrator.sagas.base import ChoiceOption, SideEffect, SlotRequest

_EXPLORATORY_PHASES = ("DREAMING", "SHAPING")

# "stop asking me anything" — mutes elicitation for the rest of the run.
_MUTE_PHRASES = (
    "no more questions", "stop asking", "don't ask", "dont ask", "no questions",
    "just go on", "go on without", "skip the questions", "skip all the questions",
    "skip these questions", "without my answers", "without answering",
    "no time for questions", "don't have time for questions",
    "dont have time for questions", "stop the questions", "enough questions",
    "quit asking", "no more of these", "just continue", "move on already",
)
# "skip just this one" — move on to the next question (soft, this run only).
_SKIP_ONE_CONTAINS = (
    "skip this", "skip that", "skip it", "next question", "i dunno", "i don't know",
    "i dont know", "no idea", "rather not say", "prefer not to", "no comment",
    "let's skip", "lets skip", "skip for now",
)
_SKIP_ONE_EXACT = ("skip", "pass", "not sure", "next", "dunno", "idk")


def elicitor_enabled() -> bool:
    """Kill switch (mirrors ``CURIOSITY_INJECTOR_ENABLED``)."""
    return os.getenv("PROFILE_ELICITOR_ENABLED", "true").strip().lower() not in (
        "0", "false", "no", "off",
    )


# ── per-run state on the trip ────────────────────────────────────────────────

def read_elicitation_state(trip: Optional[dict[str, Any]]) -> dict[str, Any]:
    """The per-run elicitation state off the trip (empty defaults when absent)."""
    raw = ((trip or {}).get("live_state") or {}).get("elicitation") or {}
    return {
        "asked": list(raw.get("asked") or []),
        "answered_flow": dict(raw.get("answered_flow") or {}),
        "muted": bool(raw.get("muted") or False),
        "pending": raw.get("pending"),
    }


def elicitation_state_side_effect(
    trip: dict[str, Any], run_state: dict[str, Any]
) -> SideEffect:
    """A ``trip_patch`` carrying the merged ``live_state`` with the new elicitation
    run-state. The JSONB column is replaced wholesale on write, so we merge here.
    ``live_state`` is uncontended during planning/discovery (only LIVING writes it)."""
    live = dict(trip.get("live_state") or {})
    live["elicitation"] = run_state
    return SideEffect(kind="trip_patch", payload={"id": trip.get("id"), "live_state": live})


# ── typed-reply classification ───────────────────────────────────────────────

def classify_elicitation_reply(message: str) -> str:
    """Classify a TYPED reply that arrives while a Traveler-DNA question is pending:
    ``"mute"`` (stop all questions this run), ``"skip"`` (skip this one — move on), or
    ``"other"`` (a real answer or an unrelated deviation — let the saga handle it).
    Pure; conservative; only consulted when a question was actually pending."""
    m = (message or "").strip().lower().rstrip("!.? ")
    if not m:
        return "other"
    if any(p in m for p in _MUTE_PHRASES):
        return "mute"
    if any(p in m for p in _SKIP_ONE_CONTAINS):
        return "skip"
    if m in _SKIP_ONE_EXACT:
        return "skip"
    return "other"


# ── the selector ─────────────────────────────────────────────────────────────

def _profile_data(user_doc: dict[str, Any]) -> dict[str, Any]:
    return ((user_doc.get("user_profile") or {}).get("profile_data")) or {}


def _structure_preference(user_doc: dict[str, Any]) -> float:
    scores = _profile_data(user_doc).get("personality_dimensions_scores") or {}
    try:
        return float(scores.get("structure_preference", 0.5))
    except (TypeError, ValueError):
        return 0.5


def _reply_length(user_doc: dict[str, Any]) -> str:
    return _profile_data(user_doc).get("reply_length_preference") or "default"


class ProfileElicitor:
    """Deterministic, no-LLM selector of the next Traveler-DNA question to weave in.
    Returns one ``SlotRequest(target='profile')`` or ``None``. NEVER mutates state;
    the caller owns persistence."""

    def next_question(
        self,
        saga: Any,
        user_doc: dict[str, Any],
        run_state: dict[str, Any],
        *,
        phase: str,
        turn_has_primary_content: bool,
        aside_budget_available: bool,
    ) -> Optional[SlotRequest]:
        if not elicitor_enabled():
            return None
        if not turn_has_primary_content or not aside_budget_available:
            return None
        if run_state.get("muted"):
            return None
        # Suppress philosophical asides for high-structure planners on exploratory turns.
        if phase in _EXPLORATORY_PHASES and _structure_preference(user_doc) > 0.7:
            return None
        # Terse users: ask less often — every other eligible turn.
        if _reply_length(user_doc) == "terse" and len(run_state.get("asked") or []) % 2 == 1:
            return None

        asked = set(run_state.get("asked") or [])
        answered_flow = set((run_state.get("answered_flow") or {}).keys())
        gap = compute_gap(saga, user_doc, flow_answered=answered_flow)

        # flow_state first (flow-critical for the active trip), then profile traits.
        flow_cands = self._rank([q for q in gap["missing_flow_state"] if q not in asked])
        profile_cands = self._rank([q for q in gap["missing_profile"] if q not in asked])
        ordered = flow_cands + profile_cands
        if not ordered:
            return None
        return self._build_request(ordered[0])

    @staticmethod
    def _rank(qids: list[str]) -> list[str]:
        """Rank by (most informative first, then tap-cost, then stable id)."""
        defs = [BY_ID[q] for q in qids if q in BY_ID]
        defs.sort(key=lambda q: (-len(q.informs), 0 if q.cost == "tap" else 1, q.id))
        return [q.id for q in defs]

    @staticmethod
    def _build_request(qid: str) -> SlotRequest:
        q = BY_ID[qid]
        choices = [ChoiceOption(c.id, c.label, c.value) for c in q.choices]
        choices.append(ChoiceOption("skip", "Skip", "__skip__"))
        return SlotRequest(
            slot=qid,
            prompt=q.prompt,
            choices=choices,
            allow_multi=q.allow_multi,
            target="profile",
        )
