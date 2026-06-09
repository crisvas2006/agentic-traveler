"""Parity tests for derive_saga_state_local vs public.derive_saga_state (Task 36).

Mirrors the branch order of the SQL function. No DB / LLM.
"""

from datetime import date, timedelta

from agentic_traveler.orchestrator.sagas.saga_state import derive_saga_state_local

TODAY = date(2027, 6, 1)


def _trip(**overrides):
    base = {
        "id": "t1",
        "status": "dreaming",
        "discovery": {},
        "preferences": {},
        "travelers": {},
        "destinations": [],
        "bookings": [],
    }
    base.update(overrides)
    return base


def test_none_trip_is_dreaming():
    assert derive_saga_state_local(None, TODAY) == "DREAMING"


def test_empty_trip_is_dreaming():
    assert derive_saga_state_local(_trip(), TODAY) == "DREAMING"


def test_considering_destination_is_shaping():
    trip = _trip(destinations=[{"name": "Iceland", "status": "considering"}])
    assert derive_saga_state_local(trip, TODAY) == "SHAPING"


def test_confirmed_destination_with_start_is_anchoring():
    trip = _trip(
        destinations=[{"name": "Iceland", "status": "confirmed"}],
        discovery={"timeframe": {"start_date": "2027-09-01"}},
    )
    assert derive_saga_state_local(trip, TODAY) == "ANCHORING"


def test_confirmed_without_start_is_shaping():
    trip = _trip(destinations=[{"name": "Iceland", "status": "confirmed"}])
    assert derive_saga_state_local(trip, TODAY) == "SHAPING"


def test_all_prereqs_met_is_detailing():
    trip = _trip(
        destinations=[{"name": "Iceland", "status": "confirmed"}],
        discovery={"timeframe": {"start_date": "2027-09-01"}},
        preferences={"pace": "slow", "structure": "loose", "budget_tier": "$$"},
        travelers={"count": 2},
    )
    assert derive_saga_state_local(trip, TODAY) == "DETAILING"


def test_any_booking_is_detailing():
    trip = _trip(
        destinations=[{"name": "Iceland", "status": "confirmed"}],
        bookings=[{"kind": "flight"}],
    )
    assert derive_saga_state_local(trip, TODAY) == "DETAILING"


def test_today_within_window_is_living():
    trip = _trip(
        discovery={"timeframe": {
            "start_date": str(TODAY - timedelta(days=2)),
            "end_date": str(TODAY + timedelta(days=5)),
        }},
    )
    assert derive_saga_state_local(trip, TODAY) == "LIVING"


def test_recently_ended_is_remembering():
    trip = _trip(
        discovery={"timeframe": {
            "start_date": str(TODAY - timedelta(days=20)),
            "end_date": str(TODAY - timedelta(days=10)),
        }},
    )
    assert derive_saga_state_local(trip, TODAY) == "REMEMBERING"


def test_imminent_departure_is_ready_to_go():
    trip = _trip(
        destinations=[{"name": "Iceland", "status": "confirmed"}],
        discovery={"timeframe": {"start_date": str(TODAY + timedelta(days=3))}},
    )
    assert derive_saga_state_local(trip, TODAY) == "READY_TO_GO"


def test_presence_semantics_empty_string_pace_still_counts():
    # SQL uses `preferences ? 'pace'` (key presence), not truthiness.
    trip = _trip(
        destinations=[{"name": "Iceland", "status": "confirmed"}],
        discovery={"timeframe": {"start_date": "2027-09-01"}},
        preferences={"pace": "", "structure": "", "budget_tier": ""},
        travelers={"count": 2},
    )
    assert derive_saga_state_local(trip, TODAY) == "DETAILING"
