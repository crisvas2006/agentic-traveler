"""Integration test for PlanningSaga (Task 36 AC-9)."""

from unittest.mock import patch, MagicMock
import pytest
from agentic_traveler.orchestrator.sagas.planning import PlanningSaga
from agentic_traveler.orchestrator.event_emitter import EventEmitter

_EXTRACT = "agentic_traveler.orchestrator.sagas.planning.extract_trip_slots"

@pytest.fixture
def saga():
    with patch("agentic_traveler.orchestrator.sagas.planning.PlannerAgent"), \
         patch("agentic_traveler.orchestrator.sagas.planning.TripAgent"):
        s = PlanningSaga(client=MagicMock())
    s._planner = MagicMock()
    s._trip_agent = MagicMock()
    s._planner.process_request.return_value = {
        "text": "Here is your day-by-day plan.",
        "_raw_response": None, "_latency_ms": 1.0, "_search_responses": [],
    }
    s._trip_agent.process_request.return_value = {
        "text": "Some destination ideas.",
        "_raw_response": None, "_latency_ms": 1.0, "_search_responses": [],
    }
    return s

def _events():
    return EventEmitter(user_id="u1", trip_id="t1")

def _trip(**kw):
    base = {
        "id": "t1", "status": "dreaming",
        "discovery": {}, "preferences": {}, "travelers": {},
        "destinations": [], "bookings": [],
    }
    base.update(kw)
    return base

def test_integration_three_turns_to_planner(saga):
    """End-to-end multi-turn test checking that it asks pace, then structure, then delegates (AC-9)."""
    t = _trip(
        destinations=[{"name": "Iceland", "status": "considering"}],
        discovery={"timeframe": {"text": "late Jan"}},
        travelers={"count": 2},
    )
    events = _events()
    
    # Turn 1: User says "We want a slow pace"
    with patch(_EXTRACT, return_value={"pace": "slow"}):
        result1 = saga.run("We want a slow pace", {}, t, {}, "", events)
        
    assert result1.slot_request is not None
    assert result1.slot_request.slot == "structure"
    
    # Turn 2: User says "Loose structure"
    # Update trip with previous turn's side effect
    t["preferences"] = {"pace": "slow"}
    with patch(_EXTRACT, return_value={"structure": "loose"}):
        result2 = saga.run("Loose structure", {}, t, {}, "", events)
        
    assert result2.slot_request is not None
    assert result2.slot_request.slot == "budget_tier"
    
    # Turn 3: User says "$$"
    t["preferences"]["structure"] = "loose"
    with patch(_EXTRACT, return_value={"budget_tier": "$$"}):
        result3 = saga.run("$$", {}, t, {}, "", events)
        
    # All slots filled -> Planner
    saga._planner.process_request.assert_called_once()
    assert result3.text == "Here is your day-by-day plan."
