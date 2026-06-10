"""Destination brief tests (task 45). Gemini mocked per TESTING_STRATEGY.md."""

from unittest.mock import patch

from agentic_traveler.orchestrator.event_emitter import EventEmitter
from agentic_traveler.orchestrator.sagas.destination_brief import (
    capture_destination_brief,
    ensure_brief,
)

_VALID = (
    '{"destination": "Taormina, Sicily",'
    ' "best_windows": [{"months": ["JUN"], "why": "warm sea, quiet lanes",'
    ' "crowd_level": "medium", "price_level": "medium"}],'
    ' "avoid_windows": [{"months": ["AUG"], "why": "peak heat and crowds"}],'
    ' "seasonal_character": {"peak": "Jul-Aug", "shoulder": "May, Sep", "low": "winter"},'
    ' "signature_experiences": ["Greek theatre at dusk", "Isola Bella swim", "granita"],'
    ' "fit_hooks": ["slow-mornings", "food-led", "walkable"]}'
)


class _Resp:
    def __init__(self, text):
        self.text = text


def _events():
    return EventEmitter(user_id="u1", trip_id="t1")


def _names(events):
    return [r["event_name"] for r in events._metric_buffer]


def _trip(dest_name="Taormina, Sicily", discovery=None, status="confirmed"):
    return {
        "id": "trip-1",
        "destinations": [{"name": dest_name, "status": status}] if dest_name else [],
        "discovery": discovery or {},
    }


# ── capture ──────────────────────────────────────────────────────────────────

def test_capture_happy_path():
    with patch(
        "agentic_traveler.orchestrator.sagas.destination_brief.gemini_generate",
        return_value=_Resp(_VALID),
    ):
        brief = capture_destination_brief(object(), "Taormina, Sicily", {})
    assert brief["destination"] == "Taormina, Sicily"
    assert brief["fit_hooks"][0] == "slow-mornings"
    assert brief["best_windows"][0]["months"] == ["JUN"]
    assert "captured_at" in brief and brief["model_version"]


def test_capture_malformed_json_returns_none():
    with patch(
        "agentic_traveler.orchestrator.sagas.destination_brief.gemini_generate",
        return_value=_Resp("not json"),
    ):
        assert capture_destination_brief(object(), "Nowhere", {}) is None


def test_capture_no_client_returns_none():
    assert capture_destination_brief(None, "Taormina", {}) is None


# ── ensure_brief ─────────────────────────────────────────────────────────────

def test_ensure_brief_no_destination_returns_none():
    events = _events()
    assert ensure_brief(object(), _trip(dest_name=None), {}, events) is None


def test_ensure_brief_captures_and_writes_into_discovery():
    events = _events()
    with patch(
        "agentic_traveler.orchestrator.sagas.destination_brief.gemini_generate",
        return_value=_Resp(_VALID),
    ):
        se = ensure_brief(object(), _trip(discovery={"vision_summary": "x"}), {}, events)
    assert se is not None and se.kind == "trip_patch"
    disc = se.payload["discovery"]
    assert disc["destination_brief"]["destination"] == "Taormina, Sicily"
    # Merge, not replace — sibling discovery keys survive.
    assert disc["vision_summary"] == "x"
    ok = [r for r in events._metric_buffer if r["event_name"] == "brief_captured"]
    assert ok and ok[0]["payload"]["ok"] is True


def test_ensure_brief_idempotent_when_brief_for_same_destination():
    events = _events()
    trip = _trip(discovery={"destination_brief": {"destination": "Taormina, Sicily"}})
    with patch(
        "agentic_traveler.orchestrator.sagas.destination_brief.gemini_generate",
    ) as gen:
        se = ensure_brief(object(), trip, {}, events)
    assert se is None
    gen.assert_not_called()


def test_ensure_brief_recaptures_when_destination_changed():
    events = _events()
    trip = _trip(
        dest_name="Lisbon, Portugal",
        discovery={"destination_brief": {"destination": "Taormina, Sicily"}},
    )
    lisbon = _VALID.replace("Taormina, Sicily", "Lisbon, Portugal")
    with patch(
        "agentic_traveler.orchestrator.sagas.destination_brief.gemini_generate",
        return_value=_Resp(lisbon),
    ):
        se = ensure_brief(object(), trip, {}, events)
    assert se is not None
    assert se.payload["discovery"]["destination_brief"]["destination"] == "Lisbon, Portugal"


def test_ensure_brief_capture_failure_emits_not_ok_and_no_side_effect():
    events = _events()
    with patch(
        "agentic_traveler.orchestrator.sagas.destination_brief.gemini_generate",
        return_value=_Resp("garbage"),
    ):
        se = ensure_brief(object(), _trip(), {}, events)
    assert se is None
    rows = [r for r in events._metric_buffer if r["event_name"] == "brief_captured"]
    assert rows and rows[0]["payload"]["ok"] is False
