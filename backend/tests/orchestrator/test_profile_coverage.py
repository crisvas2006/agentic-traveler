"""Task 54 — saga coverage gap + answered-id resolution."""

from agentic_traveler.orchestrator.profile_coverage import (
    answered_profile_ids,
    compute_gap,
)


class _Saga:
    requires_profile = ["travel_company", "pace", "budget_tier"]
    asks_flow_state = ["current_craving"]


def _doc(answered=None, overrides=None):
    pd: dict = {}
    if answered is not None:
        pd["answered_questions"] = answered
    if overrides is not None:
        pd["hard_overrides"] = overrides
    return {"user_profile": {"profile_data": pd}}


def test_answered_ids_from_answered_questions():
    doc = _doc(answered={"travel_company": {"value": "duo", "source": "chat_tap"}})
    assert "travel_company" in answered_profile_ids(doc)


def test_hard_override_counts_as_answered():
    # budget_tier.hard_override_slot == "ask.budget" (AC-7)
    doc = _doc(overrides=[{"slot": "ask.budget", "value": "high_end"}])
    assert "budget_tier" in answered_profile_ids(doc)


def test_compute_gap_overlap_and_flow():
    doc = _doc(answered={"travel_company": {"value": "duo"}})
    gap = compute_gap(_Saga(), doc, flow_answered=set())
    assert "travel_company" not in gap["missing_profile"]
    assert set(gap["missing_profile"]) == {"pace", "budget_tier"}
    assert gap["missing_flow_state"] == ["current_craving"]


def test_compute_gap_flow_answered_this_run():
    gap = compute_gap(_Saga(), _doc(), flow_answered={"current_craving"})
    assert gap["missing_flow_state"] == []


def test_compute_gap_empty_for_saga_with_no_requirements():
    class Bare:
        pass

    assert compute_gap(Bare(), _doc()) == {"missing_profile": [], "missing_flow_state": []}
