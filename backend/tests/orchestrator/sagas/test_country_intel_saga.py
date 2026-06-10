from agentic_traveler.orchestrator.sagas.country_intel import CountryIntelSaga
from agentic_traveler.tools.country_intel_fetcher import compute_safety_score_10, user_threshold

def test_compute_safety_score_10():
    # advisory_level 1 (best) -> 10, plus gpi <=50 (+1.5) -> 11.5, capped at 10
    assert compute_safety_score_10(1, 10, 0.0) == 10.0
    
    # advisory 3 -> 4.0, crime_signal 2.0 -> -1.0 = 3.0
    assert compute_safety_score_10(3, None, 2.0) == 3.0
    
    # worst case: advisory 4 -> 1.0, gpi 120 -> -1.5, crime 1.0 -> -0.5 = -1.0 capped at 0.0
    assert compute_safety_score_10(4, 120, 1.0) == 0.0

def test_user_threshold():
    # High risk appetite -> lower threshold
    assert user_threshold({"personality_dimensions_scores": {"risk_appetite": 0.8}}) == 5.0
    # Low risk appetite -> higher threshold
    assert user_threshold({"personality_dimensions_scores": {"risk_appetite": 0.2}}) == 8.0
    # Medium risk appetite -> default
    assert user_threshold({"personality_dimensions_scores": {"risk_appetite": 0.5}}) == 7.0

def test_saga_activation_as_listener():
    saga = CountryIntelSaga(client=None)
    entities = {
        "side_effects_seen": [
            {"kind": "destination_upsert", "payload": {"status": "confirmed", "iso_country": "JP"}}
        ]
    }
    can_act, wants_to_own = saga.should_activate("CHAT", entities, trip=None, state={})
    assert can_act is True
    assert wants_to_own is False

def test_saga_activation_as_owner():
    saga = CountryIntelSaga(client=None)
    entities = {"intel_question": True}
    can_act, wants_to_own = saga.should_activate("CHAT", entities, trip=None, state={})
    assert can_act is True
    assert wants_to_own is True
