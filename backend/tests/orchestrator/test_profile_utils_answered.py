"""Task 54 — answered-summary line + relevant_dimensions in profile_utils."""

from agentic_traveler.orchestrator.profile_utils import (
    build_profile_summary,
    relevant_dimensions,
)


def _doc(profile_data):
    return {"name": "Cris", "user_profile": {"profile_data": profile_data, "summary": "S"}}


def test_answered_line_present_and_not_dumped_raw():
    pd = {
        "answered_questions": {
            "pace": {"value": "slow", "source": "chat_tap"},
            "travel_company": {"value": "duo"},
        }
    }
    out = build_profile_summary(_doc(pd))
    assert "Answered:" in out
    assert "pace=slow" in out
    assert "answered_questions" not in out  # raw dict must not be dumped (AC-10)


def test_multi_value_joined():
    pd = {"answered_questions": {"deal_breakers": {"value": ["no_wifi", "crowds"]}}}
    out = build_profile_summary(_doc(pd))
    assert "deal_breakers=no_wifi/crowds" in out


def test_skip_and_empty_excluded():
    pd = {"answered_questions": {"pace": {"value": "__skip__"}, "budget_tier": {"value": ""}}}
    out = build_profile_summary(_doc(pd))
    assert "Answered:" not in out


def test_no_answered_questions_unchanged():
    out = build_profile_summary(_doc({"tags": ["foo"]}))
    assert "Answered:" not in out


class _Saga:
    requires_profile = ["travel_company", "pace"]


def test_relevant_dimensions_union():
    dims = relevant_dimensions(_Saga())
    assert {"social_energy", "travel_company", "pace", "energy_strategy"} <= dims


def test_relevant_dimensions_empty_saga():
    class Bare:
        pass

    assert relevant_dimensions(Bare()) == set()
