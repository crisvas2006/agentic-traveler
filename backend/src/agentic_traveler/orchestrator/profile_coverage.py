"""Task 54 — saga-scoped Traveler-DNA coverage.

A saga declares the question ids it needs to personalise well:
  - ``requires_profile`` — stable-trait (``profile``) questions; answered once and
    reused across sagas (overlap is shared).
  - ``asks_flow_state`` — current-state (``flow_state``) questions; re-asked each
    flow run (never persisted to the durable profile).

``compute_gap`` returns what is still missing for a saga, so the elicitor (Task 55)
knows what to weave in. Pure functions, no LLM, no I/O.
"""

from __future__ import annotations

from typing import Any

from agentic_traveler.orchestrator.profile_questions import BY_ID


def _profile_data(user_doc: dict[str, Any]) -> dict[str, Any]:
    return ((user_doc.get("user_profile") or {}).get("profile_data")) or {}


def answered_profile_ids(user_doc: dict[str, Any]) -> set[str]:
    """Profile question ids considered answered for this user: ids present in
    ``profile_data.answered_questions`` PLUS ids whose ``hard_override_slot`` is
    satisfied in ``profile_data.hard_overrides`` (Task 54 AC-7)."""
    pd = _profile_data(user_doc)
    ids: set[str] = set((pd.get("answered_questions") or {}).keys())

    override_slots = {
        o.get("slot")
        for o in (pd.get("hard_overrides") or [])
        if isinstance(o, dict) and o.get("slot")
    }
    if override_slots:
        for qid, q in BY_ID.items():
            if (
                q.binding == "profile"
                and q.hard_override_slot
                and q.hard_override_slot in override_slots
            ):
                ids.add(qid)
    return ids


def compute_gap(
    saga: Any, user_doc: dict[str, Any], flow_answered: set[str] | None = None
) -> dict[str, list[str]]:
    """``{'missing_profile': [...], 'missing_flow_state': [...]}`` for ``saga``.

    ``flow_answered`` is the set of ``flow_state`` ids answered *this flow run*
    (ephemeral; carried on SagaState / conversation state, never the profile).
    Overlap and hard-overrides are honoured via :func:`answered_profile_ids`.
    """
    flow_answered = flow_answered or set()
    answered = answered_profile_ids(user_doc)

    missing_profile = [
        qid
        for qid in (getattr(saga, "requires_profile", []) or [])
        if qid in BY_ID and BY_ID[qid].binding == "profile" and qid not in answered
    ]
    missing_flow_state = [
        qid
        for qid in (getattr(saga, "asks_flow_state", []) or [])
        if qid in BY_ID and BY_ID[qid].binding == "flow_state" and qid not in flow_answered
    ]
    return {"missing_profile": missing_profile, "missing_flow_state": missing_flow_state}
