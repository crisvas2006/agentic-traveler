"""Router `trip_directive` parsing (Task 44).

Exercises the static JSON parser only — no LLM / DB.
"""

import json

from agentic_traveler.orchestrator.router_agent import RouterAgent


def _parse(payload: dict):
    return RouterAgent._parse(json.dumps(payload), "msg")


def test_directive_continue():
    assert _parse({"intent": "PLAN", "trip_directive": "continue"})["trip_directive"] == "continue"


def test_directive_new():
    assert _parse({"intent": "PLAN", "trip_directive": "new"})["trip_directive"] == "new"


def test_directive_unspecified_explicit():
    assert _parse({"intent": "PLAN", "trip_directive": "unspecified"})["trip_directive"] == "unspecified"


def test_directive_absent_defaults_to_unspecified():
    assert _parse({"intent": "CHAT"})["trip_directive"] == "unspecified"


def test_directive_invalid_value_falls_back():
    assert _parse({"intent": "PLAN", "trip_directive": "switcheroo"})["trip_directive"] == "unspecified"


def test_directive_null_falls_back():
    assert _parse({"intent": "TRIP", "trip_directive": None})["trip_directive"] == "unspecified"


def test_parse_failure_fallback_carries_directive():
    assert RouterAgent._parse("not json", "msg")["trip_directive"] == "unspecified"
