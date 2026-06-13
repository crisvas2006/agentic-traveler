"""Task 55 — ProfileElicitor selection + erratic-reply classification + run-state."""

from agentic_traveler.orchestrator.profile_elicitor import (
    ProfileElicitor,
    classify_elicitation_reply,
    elicitation_state_side_effect,
    read_elicitation_state,
)
from agentic_traveler.orchestrator.profile_questions import BY_ID


class _Saga:
    name = "PlanningSaga"
    requires_profile = ["meaning_depth", "immersion"]
    asks_flow_state = ["trip_intent_this_time", "energy_for_this_trip"]


def _doc(structure=0.5, reply_len="default", answered=None):
    pd = {
        "personality_dimensions_scores": {"structure_preference": structure},
        "reply_length_preference": reply_len,
    }
    if answered:
        pd["answered_questions"] = answered
    return {"user_profile": {"profile_data": pd}}


def _state(asked=None, answered_flow=None, muted=False):
    return {
        "asked": list(asked or []),
        "answered_flow": dict(answered_flow or {}),
        "muted": muted,
        "pending": None,
    }


E = ProfileElicitor()


def _next(saga, doc, state, phase="ANCHORING", primary=True, aside=True):
    return E.next_question(
        saga, doc, state, phase=phase,
        turn_has_primary_content=primary, aside_budget_available=aside,
    )


# ── selection ────────────────────────────────────────────────────────────────

def test_returns_none_when_no_requirements():
    class Bare:
        name = "X"

    assert _next(Bare(), _doc(), _state()) is None


def test_returns_one_profile_chip_with_skip_and_target():
    sr = _next(_Saga(), _doc(), _state())
    assert sr is not None
    assert sr.target == "profile"
    assert sr.choices[-1].value == "__skip__"  # mutually-exclusive Skip appended
    assert len(sr.prompt) <= 200


def test_flow_state_prioritised_over_profile():
    sr = _next(_Saga(), _doc(), _state())
    assert BY_ID[sr.slot].binding == "flow_state"


def test_no_primary_content_or_no_aside_budget_yields_none():
    assert _next(_Saga(), _doc(), _state(), primary=False) is None
    assert _next(_Saga(), _doc(), _state(), aside=False) is None


def test_muted_run_yields_none():
    assert _next(_Saga(), _doc(), _state(muted=True)) is None


def test_high_structure_suppressed_only_on_exploratory_phase():
    doc = _doc(structure=0.82)
    assert _next(_Saga(), doc, _state(), phase="DREAMING") is None
    assert _next(_Saga(), doc, _state(), phase="ANCHORING") is not None


def test_terse_user_asks_every_other_turn():
    doc = _doc(reply_len="terse")
    assert _next(_Saga(), doc, _state(asked=[])) is not None  # even count → ask
    assert _next(_Saga(), doc, _state(asked=["trip_intent_this_time"])) is None  # odd → skip


def test_asked_questions_not_re_offered_this_run():
    state = _state(asked=["trip_intent_this_time", "energy_for_this_trip"])
    sr = _next(_Saga(), _doc(), state)
    # both flow_state asked → next must be a profile trait, not a re-ask
    assert sr is not None and sr.slot in ("meaning_depth", "immersion")


def test_answered_flow_excluded_from_gap():
    state = _state(answered_flow={"trip_intent_this_time": "reset", "energy_for_this_trip": "high"})
    sr = _next(_Saga(), _doc(), state)
    assert sr is not None and BY_ID[sr.slot].binding == "profile"


def test_full_run_cycle_then_none():
    # Offer each needed question exactly once across turns, then stop.
    state = _state()
    seen = []
    for _ in range(6):
        sr = _next(_Saga(), _doc(), state)
        if sr is None:
            break
        seen.append(sr.slot)
        state["asked"].append(sr.slot)
    assert set(seen) == {
        "trip_intent_this_time", "energy_for_this_trip", "meaning_depth", "immersion",
    }
    assert _next(_Saga(), _doc(), state) is None  # all asked → done


def test_answered_profile_question_not_offered():
    doc = _doc(answered={"meaning_depth": {"value": "seeker"}})
    state = _state(asked=["trip_intent_this_time", "energy_for_this_trip"])
    sr = _next(_Saga(), doc, state)
    assert sr is not None and sr.slot == "immersion"  # meaning_depth already answered


# ── erratic typed replies (the user's scenarios) ──────────────────────────────

def test_classify_mute_phrases():
    assert classify_elicitation_reply(
        "I don't have time for questions, just go on without my answers"
    ) == "mute"
    assert classify_elicitation_reply("no more questions please") == "mute"
    assert classify_elicitation_reply("stop asking me stuff") == "mute"


def test_classify_skip_phrases():
    assert classify_elicitation_reply("I dunno, let's skip this question") == "skip"
    assert classify_elicitation_reply("skip") == "skip"
    assert classify_elicitation_reply("not sure") == "skip"
    assert classify_elicitation_reply("pass") == "skip"


def test_classify_other_is_answer_or_deviation():
    assert classify_elicitation_reply("slow and steady, please") == "other"
    assert classify_elicitation_reply("what's the weather in Tokyo?") == "other"
    assert classify_elicitation_reply("") == "other"


# ── run-state helpers ─────────────────────────────────────────────────────────

def test_read_elicitation_state_defaults():
    rs = read_elicitation_state(None)
    assert rs == {"asked": [], "answered_flow": {}, "muted": False, "pending": None}


def test_elicitation_state_side_effect_merges_live_state():
    trip = {"id": "t1", "live_state": {"current_day_n": 3}}
    rs = _state(asked=["meaning_depth"], muted=True)
    se = elicitation_state_side_effect(trip, rs)
    assert se.kind == "trip_patch"
    assert se.payload["id"] == "t1"
    assert se.payload["live_state"]["current_day_n"] == 3  # preserved
    assert se.payload["live_state"]["elicitation"]["muted"] is True
