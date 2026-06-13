"""Task 55 — orchestrator-level elicitation glue (_maybe_elicit_profile).

Exercises the weave/skip/mute orchestration against a minimal fake orchestrator so
no real client/DB is constructed. The selection + classification logic itself is
covered by test_profile_elicitor.py.
"""

from agentic_traveler.orchestrator.agent import OrchestratorAgent
from agentic_traveler.orchestrator.sagas.base import SagaResult, SlotRequest


class _Owner:
    name = "PlanningSaga"
    requires_profile = ["meaning_depth", "immersion"]
    asks_flow_state = ["trip_intent_this_time", "energy_for_this_trip"]


class _Events:
    def emit(self, *a, **k):  # noqa: D401 - test stub
        pass


class _FakeOrch:
    """Stand-in exposing only the methods under test + a recording apply."""

    _maybe_elicit_profile = OrchestratorAgent._maybe_elicit_profile
    _is_exploratory = staticmethod(OrchestratorAgent._is_exploratory)

    def __init__(self):
        self.applied: list = []

    def _apply_side_effects(self, user_id, side_effects):
        self.applied.extend(side_effects)


def _doc():
    return {"user_profile": {"profile_data": {
        "personality_dimensions_scores": {"structure_preference": 0.5}
    }}}


def _trip(elicitation=None):
    trip = {"id": "t1", "destinations": [{"status": "confirmed"}], "live_state": {}}
    if elicitation is not None:
        trip["live_state"]["elicitation"] = elicitation
    return trip


def test_offers_question_and_persists_runstate():
    orch = _FakeOrch()
    result = SagaResult(text="Here's a thought on Kyoto.")
    orch._maybe_elicit_profile(_Owner(), "tell me about kyoto", _doc(), _trip(), result, "u1", _Events())

    assert result.slot_request is not None
    assert result.slot_request.target == "profile"
    assert len(orch.applied) == 1
    elic = orch.applied[0].payload["live_state"]["elicitation"]
    assert elic["pending"] == result.slot_request.slot
    assert result.slot_request.slot in elic["asked"]


def test_does_not_stack_when_saga_already_asked():
    orch = _FakeOrch()
    existing = SlotRequest(slot="destination", prompt="Where to?")
    result = SagaResult(text="...", slot_request=existing)
    orch._maybe_elicit_profile(_Owner(), "hi", _doc(), _trip(), result, "u1", _Events())

    assert result.slot_request is existing  # the trip slot is untouched (AC-5/AC-9)
    assert orch.applied == []  # nothing pending → nothing to persist


def test_mute_phrase_sets_muted_and_offers_nothing():
    orch = _FakeOrch()
    trip = _trip({"asked": ["meaning_depth"], "answered_flow": {}, "muted": False, "pending": "meaning_depth"})
    result = SagaResult(text="Sure, continuing.")
    orch._maybe_elicit_profile(
        _Owner(),
        "I don't have time for questions, just go on without my answers",
        _doc(), trip, result, "u1", _Events(),
    )

    assert result.slot_request is None  # muted → no new question
    assert len(orch.applied) == 1
    assert orch.applied[0].payload["live_state"]["elicitation"]["muted"] is True


def test_skip_reply_moves_on_without_muting():
    orch = _FakeOrch()
    trip = _trip({"asked": ["trip_intent_this_time"], "answered_flow": {}, "muted": False,
                  "pending": "trip_intent_this_time"})
    result = SagaResult(text="No problem.")
    orch._maybe_elicit_profile(_Owner(), "eh, skip this one", _doc(), trip, result, "u1", _Events())

    # skip-one is not mute: a different next question is offered, run continues.
    assert result.slot_request is not None
    elic = orch.applied[-1].payload["live_state"]["elicitation"]
    assert elic["muted"] is False
    assert result.slot_request.slot != "trip_intent_this_time"  # not re-asked


def test_no_trip_degrades_gracefully():
    orch = _FakeOrch()
    result = SagaResult(text="A dreamy idea, no pressure.")
    orch._maybe_elicit_profile(_Owner(), "somewhere warm", _doc(), None, result, "u1", _Events())

    # Without a trip the question can still be offered, but run-state can't persist.
    assert orch.applied == []
