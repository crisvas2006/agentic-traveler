"""JournalSaga unit tests (task 41).

Covers the REMEMBERING-window activation, the once-per-day owner prompt, the
listener capture of reflections, and the structure extraction. Gemini is
patched; no real calls.
"""

from datetime import date, timedelta
from unittest.mock import patch

from agentic_traveler.orchestrator.event_emitter import EventEmitter
from agentic_traveler.orchestrator.sagas.journal import JournalSaga, structure_journal


def _events():
    return EventEmitter(user_id="u1", trip_id="t1")


def _metric_names(events):
    return [r["event_name"] for r in events._metric_buffer]


def _remembering_trip(**journal):
    """Trip that ended 5 days ago → derive_saga_state == REMEMBERING."""
    today = date.today()
    return {
        "id": "trip-1",
        "status": "past",
        "discovery": {
            "timeframe": {
                "start_date": (today - timedelta(days=12)).isoformat(),
                "end_date": (today - timedelta(days=5)).isoformat(),
            }
        },
        "journal": dict(journal),
        "destinations": [{"name": "Kyoto, Japan", "status": "confirmed"}],
    }


def _active_trip():
    today = date.today()
    return {
        "id": "trip-1",
        "discovery": {"timeframe": {
            "start_date": (today - timedelta(days=1)).isoformat(),
            "end_date": (today + timedelta(days=3)).isoformat(),
        }},
        "journal": {},
        "destinations": [{"name": "Kyoto, Japan", "status": "confirmed"}],
    }


# ── activation (AC-5) ────────────────────────────────────────────────────────

def test_inactive_without_trip():
    assert JournalSaga().should_activate("CHAT", {}, None, {}) == (False, False)


def test_inactive_when_not_remembering():
    assert JournalSaga().should_activate("CHAT", {}, _active_trip(), {}) == (False, False)


def test_owner_on_chat_when_not_prompted_today():
    # A low-substance CHAT turn in REMEMBERING → owns to offer one prompt.
    assert JournalSaga().should_activate("CHAT", {}, _remembering_trip(), {}) == (True, True)


def test_listener_on_chat_when_already_prompted_today():
    trip = _remembering_trip(last_prompt_date=date.today().isoformat())
    assert JournalSaga().should_activate("CHAT", {}, trip, {}) == (True, False)


def test_listener_on_substantive_intent():
    # A travel question (TRIP) must be answered by the companion, not hijacked
    # by a journal prompt — JournalSaga only listens (to capture reflections).
    assert JournalSaga().should_activate("TRIP", {}, _remembering_trip(), {}) == (True, False)


# ── structure extraction (AC-7) ──────────────────────────────────────────────

def test_structure_journal_extracts_fields():
    class _Resp:
        text = (
            '{"is_reflection": true, "entry_text": "Tofuku-ji in the rain was the highlight.",'
            ' "day_n": 3, "highlights": ["moss garden in the rain"], "regrets": []}'
        )

    with patch(
        "agentic_traveler.orchestrator.sagas.journal.gemini_generate",
        return_value=_Resp(),
    ):
        out = structure_journal(object(), "Tofuku-ji in the rain was the highlight, day 3.")
    assert out["is_reflection"] is True
    assert out["entry_text"].startswith("Tofuku-ji")
    assert out["day_n"] == 3
    assert out["highlights"] == ["moss garden in the rain"]


def test_structure_journal_non_reflection():
    class _Resp:
        text = '{"is_reflection": false}'

    with patch(
        "agentic_traveler.orchestrator.sagas.journal.gemini_generate",
        return_value=_Resp(),
    ):
        out = structure_journal(object(), "hey")
    assert out["is_reflection"] is False


# ── run: owner offers a prompt (AC-6, AC-8) ──────────────────────────────────

def test_run_owner_offers_prompt():
    saga = JournalSaga()
    events = _events()
    trip = _remembering_trip()

    # Non-reflection greeting → ask one of the three prompts.
    with patch(
        "agentic_traveler.orchestrator.sagas.journal.structure_journal",
        return_value={"is_reflection": False},
    ):
        result = saga.run("hey there", {}, trip, {"intent": "CHAT"}, "", events)

    assert result.text in (
        "What stuck with you?", "What surprised you?", "What would you do differently?",
    )
    assert result.side_effects[0].payload["journal"]["last_prompt_date"] == date.today().isoformat()
    assert "journal_prompt_offered" in _metric_names(events)


def test_run_captures_reflection_as_listener():
    saga = JournalSaga()
    events = _events()
    trip = _remembering_trip(entries=[{"text": "earlier note"}])

    with patch(
        "agentic_traveler.orchestrator.sagas.journal.structure_journal",
        return_value={
            "is_reflection": True,
            "entry_text": "The moss garden was unforgettable.",
            "day_n": 3,
            "highlights": ["moss garden"],
            "regrets": [],
        },
    ):
        result = saga.run(
            "The moss garden was unforgettable.", {}, trip, {"intent": "TRIP"}, "", events)

    # Listener: captures silently (no owned reply text).
    assert result.text is None
    j = result.side_effects[0].payload["journal"]
    assert len(j["entries"]) == 2  # appended, not replaced
    assert j["entries"][-1]["text"] == "The moss garden was unforgettable."
    assert "moss garden" in j["highlights"]
    assert "journal_entry_captured" in _metric_names(events)


def test_run_owner_captures_reflection_and_acks():
    saga = JournalSaga()
    events = _events()
    trip = _remembering_trip()

    with patch(
        "agentic_traveler.orchestrator.sagas.journal.structure_journal",
        return_value={
            "is_reflection": True,
            "entry_text": "Loved the quiet temples.",
            "day_n": None,
            "highlights": ["quiet temples"],
            "regrets": [],
        },
    ):
        result = saga.run("Loved the quiet temples.", {}, trip, {"intent": "CHAT"}, "", events)

    # Owner + reflection → warm acknowledgment (not a blank prompt) + capture.
    assert result.text
    assert result.side_effects[0].payload["journal"]["entries"][-1]["text"] == "Loved the quiet temples."
    assert "journal_entry_captured" in _metric_names(events)
