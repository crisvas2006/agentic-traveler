"""Advisory-turn composer tests (task 45). Gemini mocked."""

from unittest.mock import patch

from agentic_traveler.orchestrator.sagas.advisor_turn import (
    AdvisorTurn,
    compose_advisor_turn,
)


class _Resp:
    def __init__(self, text):
        self.text = text


def _compose(text, **kw):
    """Run compose with gemini_generate patched to return `text`."""
    defaults = dict(
        mode="advise_slot", slot="timeframe", message="when should I go?",
        brief=None, dna_summary="", state_signal=None, curiosity_prompt=None,
        conversation_context="", char_cap=350,
    )
    defaults.update(kw)
    with patch(
        "agentic_traveler.orchestrator.sagas.advisor_turn.gemini_generate",
        return_value=_Resp(text),
    ):
        return compose_advisor_turn(object(), **defaults)


def test_advise_slot_parses_text_and_proposal():
    out = _compose(
        '{"reply_text": "Late September the sea is still warm and the lanes go quiet — set September?",'
        ' "proposal": {"slot": "timeframe", "value": "2099-09", "label": "September"}}'
    )
    assert isinstance(out, AdvisorTurn)
    assert "September" in out.text
    assert out.proposal == {"slot": "timeframe", "value": "2099-09", "label": "September"}
    assert out.suggestions is None


def test_suggest_mode_parses_candidates():
    out = _compose(
        '{"reply_text": "Three that fit you:",'
        ' "suggestions": [{"value": "Taormina, Sicily", "label": "Taormina", "why": "slow + sea"},'
        ' {"value": "Lisbon, Portugal", "label": "Lisbon", "why": "light + food"},'
        ' {"value": "Tbilisi, Georgia", "label": "Tbilisi", "why": "gentle stretch"}]}',
        mode="suggest", slot=None, char_cap=1200,
    )
    assert out.proposal is None
    assert [s["label"] for s in out.suggestions] == ["Taormina", "Lisbon", "Tbilisi"]


def test_orient_mode_text_only():
    out = _compose(
        '{"reply_text": "Sea and slow, or city and dense?"}',
        mode="orient", slot=None, char_cap=200,
    )
    assert out.text == "Sea and slow, or city and dense?"
    assert out.proposal is None and out.suggestions is None


def test_budget_overflow_truncates_at_sentence_boundary():
    long = "First sentence is fine. " + "x" * 500 + " trailing."
    out = _compose(f'{{"reply_text": "{long}"}}', char_cap=60)
    assert len(out.text) <= 60
    assert out.truncated is True
    assert out.text.strip().endswith(".")


def test_invalid_past_timeframe_proposal_is_dropped():
    out = _compose(
        '{"reply_text": "How about January?",'
        ' "proposal": {"slot": "timeframe", "value": "2000-01", "label": "January 2000"}}'
    )
    assert out.text == "How about January?"
    assert out.proposal is None  # past date → proposal dropped, text kept


def test_unparseable_timeframe_proposal_is_dropped():
    out = _compose(
        '{"reply_text": "Sometime warm?",'
        ' "proposal": {"slot": "timeframe", "value": "whenever", "label": "Whenever"}}'
    )
    assert out.proposal is None


def test_malformed_json_returns_none():
    out = _compose("not json at all")
    assert out is None


def test_gemini_failure_returns_none():
    with patch(
        "agentic_traveler.orchestrator.sagas.advisor_turn.gemini_generate",
        side_effect=RuntimeError("boom"),
    ):
        out = compose_advisor_turn(
            object(), mode="advise_slot", slot="timeframe", message="x",
            brief=None, dna_summary="", state_signal=None, curiosity_prompt=None,
            conversation_context="", char_cap=350,
        )
    assert out is None


def test_destination_proposal_passes_through():
    out = _compose(
        '{"reply_text": "Taormina fits you — set it?",'
        ' "proposal": {"slot": "destination", "value": "Taormina, Sicily", "label": "Taormina"}}',
        slot="destination",
    )
    assert out.proposal["value"] == "Taormina, Sicily"
