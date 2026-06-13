"""Task 54 — Traveler-DNA question bank invariants + seed/parity guards.

Validates the Python mirror (``profile_questions.py``). The TS registry
(``frontend/src/lib/profile-questions.ts``) is the canonical author surface; the
two are hand-kept in sync and this test guards the invariants the sagas rely on.
Full automated TS<->Python byte-parity tooling is deferred (Task 59 re-touches both).
"""

from agentic_traveler.orchestrator.profile_questions import (
    BY_ID,
    PROFILE_QUESTIONS,
    legal_option_values,
)

_VALID_BINDINGS = {"profile", "flow_state"}
_VALID_CATEGORIES = {"compass", "pulse", "strategy", "identity", "state"}
_VALID_COSTS = {"tap", "flash_lite"}

# Ids the sagas wire in Tasks 55/56 — they MUST exist in the seed so those
# requires_profile / asks_flow_state references resolve before Task 59 lands.
_SAGA_REQUIRED_IDS = {
    # PlanningSaga.requires_profile
    "travel_company",
    "pace",
    "budget_tier",
    "structure_preference",
    # PlanningSaga.asks_flow_state
    "trip_intent_this_time",
    "energy_for_this_trip",
    # ExplorationSaga.requires_profile
    "meaning_depth",
    "immersion",
    # ExplorationSaga.asks_flow_state
    "current_craving",
    # CountryIntelSaga.requires_profile
    "risk_appetite",
}


def test_no_duplicate_ids():
    ids = [q.id for q in PROFILE_QUESTIONS]
    assert len(ids) == len(set(ids))
    assert set(BY_ID) == set(ids)


def test_each_question_is_well_formed():
    for q in PROFILE_QUESTIONS:
        assert q.binding in _VALID_BINDINGS, q.id
        assert q.category in _VALID_CATEGORIES, q.id
        assert q.cost in _VALID_COSTS, q.id
        assert q.prompt and len(q.prompt) <= 200, q.id
        assert q.informs, q.id
        choice_ids = [c.id for c in q.choices]
        assert len(choice_ids) == len(set(choice_ids)), q.id
        choice_values = [c.value for c in q.choices]
        assert len(choice_values) == len(set(choice_values)), q.id
        # The seed is all tappable; a free-text question would have [] choices.
        if q.choices:
            assert len(q.choices) >= 2, q.id


def test_seed_includes_flow_state_trio():
    flow = {q.id for q in PROFILE_QUESTIONS if q.binding == "flow_state"}
    assert {"trip_intent_this_time", "energy_for_this_trip", "current_craving"} <= flow


def test_saga_required_ids_exist():
    missing = _SAGA_REQUIRED_IDS - set(BY_ID)
    assert not missing, f"saga-required ids missing from the bank: {missing}"


def test_legal_option_values():
    assert legal_option_values("pace") == {"fast", "medium", "slow"}
    assert legal_option_values("nonexistent") == set()
    # A multi-select question still exposes all its option values.
    assert "no_wifi" in legal_option_values("deal_breakers")
