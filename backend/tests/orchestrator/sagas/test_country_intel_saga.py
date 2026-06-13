from unittest.mock import MagicMock, patch

from agentic_traveler.orchestrator.event_emitter import EventEmitter
from agentic_traveler.orchestrator.sagas.country_intel import CountryIntelSaga
from agentic_traveler.tools.country_intel_fetcher import compute_safety_score_10, user_threshold

# The static fallback the saga must NEVER return as a turn reply (the loop bug).
_FALLBACK = "I can look up travel facts for you. Which country are you planning to visit?"


def _events():
    return EventEmitter(user_id="u1", trip_id="t1")


def _confirmed_trip(name="Kyoto", iso="JP"):
    return {
        "id": "t1",
        "destinations": [{"name": name, "status": "confirmed", "iso_country": iso}],
        "discovery": {},
    }


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


# ── AC-3: listener activation (refresh the strip, never own the reply) ────────

def test_saga_activation_as_listener_on_destination_upsert():
    saga = CountryIntelSaga(client=None)
    entities = {
        "side_effects_seen": [
            {"kind": "destination_upsert", "payload": {"status": "confirmed", "iso_country": "JP"}}
        ]
    }
    assert saga.should_activate("CHAT", entities, trip=None, state={}) == (True, False)


def test_saga_activation_as_listener_on_just_confirmed_flag():
    saga = CountryIntelSaga(client=None)
    entities = {"side_effects_seen": [{"destination_just_confirmed": True}]}
    assert saga.should_activate("CHAT", entities, trip=None, state={}) == (True, False)


# ── AC-1: the loop fix — never own without a confirmed destination ───────────

def test_intel_question_without_trip_does_not_own():
    saga = CountryIntelSaga(client=None)
    entities = {"intel_question": True}
    assert saga.should_activate("CHAT", entities, trip=None, state={}) == (False, False)


def test_intel_question_with_only_considering_destination_does_not_own():
    saga = CountryIntelSaga(client=None)
    entities = {"intel_question": True}
    trip = {"id": "t1", "destinations": [
        {"name": "Rome", "status": "considering", "iso_country": "IT"}
    ]}
    assert saga.should_activate("CHAT", entities, trip, state={}) == (False, False)


def test_intel_question_with_confirmed_destination_but_no_iso_does_not_own():
    saga = CountryIntelSaga(client=None)
    entities = {"intel_question": True}
    trip = {"id": "t1", "destinations": [{"name": "Atlantis", "status": "confirmed"}]}
    assert saga.should_activate("CHAT", entities, trip, state={}) == (False, False)


# ── AC-2: a real grounded answer exists — own the turn ───────────────────────

def test_intel_question_with_confirmed_destination_owns():
    saga = CountryIntelSaga(client=None)
    entities = {"intel_question": True}
    assert saga.should_activate("CHAT", entities, _confirmed_trip(), state={}) == (True, True)


def test_owner_run_acknowledges_refresh_and_never_returns_fallback():
    """AC-2: an owned intel turn fires the async refresh and returns the
    'I'll check the latest facts for <name>' ack — not the static fallback."""
    saga = CountryIntelSaga(client=None)
    # Replace the async fetch so no real thread/LLM/DB work runs (and no
    # un-awaited-coroutine warning pollutes the test output).
    saga._run_fetch_async = MagicMock(return_value=None)
    state = {"activation_mode": "owner"}
    with patch("agentic_traveler.orchestrator.sagas.country_intel.threading.Thread") as MockThread:
        result = saga.run(
            "do I need a visa for Japan?", {"id": "u1"}, _confirmed_trip(),
            state, {}, _events(),
        )
    MockThread.assert_called_once()          # a refresh was queued
    assert "Kyoto" in result.text
    assert result.text != _FALLBACK
    assert "I can look up travel facts" not in result.text
