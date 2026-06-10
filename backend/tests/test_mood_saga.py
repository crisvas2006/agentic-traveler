"""MoodCheckinSaga unit tests (task 41).

Covers activation rules, mood parsing (deterministic fast-path + LLM-gated
free text), the capture write, and the once-per-day nudge. Gemini is never
called for real — the free-text parser is patched per TESTING_STRATEGY.md.
"""

from datetime import date, timedelta
from unittest.mock import patch

from agentic_traveler.orchestrator.event_emitter import EventEmitter
from agentic_traveler.orchestrator.sagas.mood_checkin import (
    MoodCheckinSaga,
    parse_mood,
)


def _events():
    return EventEmitter(user_id="u1", trip_id="t1")


def _metric_names(events):
    return [r["event_name"] for r in events._metric_buffer]


def _living_trip(**live_state):
    """A trip whose timeframe spans today → derive_saga_state == LIVING."""
    today = date.today()
    return {
        "id": "trip-1",
        "status": "active",
        "discovery": {
            "timeframe": {
                "start_date": (today - timedelta(days=2)).isoformat(),
                "end_date": (today + timedelta(days=3)).isoformat(),
            }
        },
        "live_state": dict(live_state),
        "destinations": [{"name": "Kyoto, Japan", "status": "confirmed"}],
    }


# ── activation (AC-1) ────────────────────────────────────────────────────────

def test_inactive_without_trip():
    saga = MoodCheckinSaga()
    assert saga.should_activate("CHAT", {}, None, {}) == (False, False)


def test_inactive_when_not_living():
    saga = MoodCheckinSaga()
    dreaming = {"id": "t", "discovery": {}, "destinations": []}
    assert saga.should_activate("TRIP", {}, dreaming, {}) == (False, False)


def test_listener_when_living():
    saga = MoodCheckinSaga()
    # Always a listener (never owns the reply) during LIVING.
    assert saga.should_activate("TRIP", {}, _living_trip(), {}) == (True, False)


# ── mood parsing (AC-3) ──────────────────────────────────────────────────────

def test_parse_mood_fastpath_from_livestatecard():
    # The task-40 LiveStateCard sends exactly this shape — no LLM needed.
    parsed = parse_mood(None, "Mood check-in: feeling tired today (energy 2/5).")
    assert parsed == {"label": "tired", "energy": 2}


def test_parse_mood_ignores_non_mood_without_calling_llm():
    with patch(
        "agentic_traveler.orchestrator.sagas.mood_checkin.gemini_generate"
    ) as gen:
        parsed = parse_mood(object(), "What's a good lunch spot near the station?")
    assert parsed is None
    gen.assert_not_called()


def test_parse_mood_freetext_via_llm():
    class _Resp:
        text = '{"is_mood": true, "label": "exhausted", "energy": 1}'

    with patch(
        "agentic_traveler.orchestrator.sagas.mood_checkin.gemini_generate",
        return_value=_Resp(),
    ):
        parsed = parse_mood(object(), "honestly I am completely wiped out today")
    assert parsed == {"label": "exhausted", "energy": 1}


def test_parse_mood_llm_says_not_mood():
    class _Resp:
        text = '{"is_mood": false, "label": null, "energy": null}'

    with patch(
        "agentic_traveler.orchestrator.sagas.mood_checkin.gemini_generate",
        return_value=_Resp(),
    ):
        parsed = parse_mood(object(), "feeling like the bullet train is faster")
    assert parsed is None


# ── run: capture (AC-3, AC-8) ────────────────────────────────────────────────

def test_run_captures_mood_into_live_state():
    saga = MoodCheckinSaga()
    events = _events()
    trip = _living_trip(current_day_n=3)

    result = saga.run(
        "Mood check-in: feeling good (energy 4/5).", {}, trip, {}, "", events
    )

    assert len(result.side_effects) == 1
    se = result.side_effects[0]
    assert se.kind == "trip_patch"
    assert se.payload["id"] == "trip-1"
    last = se.payload["live_state"]["last_mood"]
    assert last["label"] == "good"
    assert last["energy"] == 4
    assert "logged_at" in last
    # Existing live_state keys are preserved (merge, not replace).
    assert se.payload["live_state"]["current_day_n"] == 3
    assert "mood_logged" in _metric_names(events)


def test_double_log_overwrites_same_day():
    saga = MoodCheckinSaga()
    events = _events()
    trip = _living_trip(last_mood={"label": "tired", "energy": 2, "logged_at": date.today().isoformat() + "T08:00:00Z"})

    result = saga.run(
        "Mood check-in: feeling buzzing (energy 5/5).", {}, trip, {}, "", events
    )

    assert result.side_effects[0].payload["live_state"]["last_mood"]["label"] == "buzzing"
    assert "mood_logged" in _metric_names(events)


# ── run: nudge (AC-2, AC-8, edge: skip) ──────────────────────────────────────

def test_run_nudges_once_when_no_mood_today():
    saga = MoodCheckinSaga()
    statuses = []
    events = EventEmitter(user_id="u1", trip_id="t1", on_status=lambda p: statuses.append(p))
    trip = _living_trip()

    result = saga.run("what should I do this afternoon?", {}, trip, {}, "", events)

    assert any(s.get("phase") == "mood_check" for s in statuses)
    assert len(statuses[0]["text"]) <= 100
    assert "mood_check_skipped" in _metric_names(events)
    # Records that we prompted today so we don't nag on the next turn.
    assert result.side_effects[0].payload["live_state"]["mood_prompt_date"] == date.today().isoformat()


def test_run_no_nudge_when_already_logged_today():
    saga = MoodCheckinSaga()
    statuses = []
    events = EventEmitter(user_id="u1", trip_id="t1", on_status=lambda p: statuses.append(p))
    trip = _living_trip(last_mood={"label": "good", "energy": 4, "logged_at": date.today().isoformat() + "T09:00:00Z"})

    result = saga.run("what's the weather like?", {}, trip, {}, "", events)

    assert statuses == []
    assert result.side_effects == []
    assert "mood_check_skipped" not in _metric_names(events)


def test_run_no_nudge_when_already_prompted_today():
    saga = MoodCheckinSaga()
    statuses = []
    events = EventEmitter(user_id="u1", trip_id="t1", on_status=lambda p: statuses.append(p))
    trip = _living_trip(mood_prompt_date=date.today().isoformat())

    saga.run("any dinner ideas?", {}, trip, {}, "", events)

    assert statuses == []
