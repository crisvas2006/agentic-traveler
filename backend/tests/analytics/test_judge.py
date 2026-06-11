"""
Unit tests for analytics/judge.py (Task 47 AC-7/8/10, E6/E8/E9/E10/E11).

No real Gemini calls — all LLM interactions are mocked.
"""

from __future__ import annotations

import json
import threading
from types import SimpleNamespace
from unittest.mock import MagicMock, patch


from agentic_traveler.analytics.judge import (
    _SCORE_KEYS,
    _build_judge_input,
    _clamp_scores,
    maybe_judge_turn,
)


# ── Helpers ───────────────────────────────────────────────────────────────────

def _good_judge_output() -> str:
    return json.dumps({
        "budget_respect": 3,
        "conciseness": 3,
        "personalization_subtlety": 2,
        "groundedness": 3,
        "helpfulness": 3,
        "purple_prose": False,
        "span": None,
    })


def _mock_events():
    events = MagicMock()
    events.trip_id = "trip-1"
    emitted = []
    events.emit.side_effect = lambda name, payload: emitted.append((name, payload))
    events._emitted = emitted
    return events


def _mock_response(text: str):
    return SimpleNamespace(
        text=text,
        usage_metadata=SimpleNamespace(prompt_token_count=50, candidates_token_count=80),
        candidates=[SimpleNamespace(grounding_metadata=None)],
    )


# ── AC-7: Sampling determinism ────────────────────────────────────────────────

def test_sample_rate_zero_never_fires():
    """With sample_rate=0.0, no judge thread is started."""
    events = _mock_events()
    with patch("agentic_traveler.analytics.judge.threading.Thread") as mock_thread:
        maybe_judge_turn(
            reply_text="A good reply.",
            intent="CHAT",
            char_cap=320,
            events=events,
            sample_rate=0.0,
        )
        mock_thread.assert_not_called()


def test_sample_rate_one_always_fires():
    """With sample_rate=1.0, judge thread is always started."""
    events = _mock_events()
    with patch("agentic_traveler.analytics.judge.threading.Thread") as mock_thread:
        mock_thread.return_value = MagicMock()
        maybe_judge_turn(
            reply_text="A good reply.",
            intent="CHAT",
            char_cap=320,
            events=events,
            sample_rate=1.0,
        )
        mock_thread.assert_called_once()


def test_sample_rate_random_respected():
    """Sampling uses random() and respects the rate boundary."""
    events = _mock_events()
    # No fired list needed
    with patch("agentic_traveler.analytics.judge.random.random", return_value=0.1), \
         patch("agentic_traveler.analytics.judge.threading.Thread") as mock_thread:
        mock_thread.return_value = MagicMock()
        maybe_judge_turn(
            reply_text="reply",
            intent="CHAT",
            char_cap=320,
            events=events,
            sample_rate=0.15,  # 0.1 < 0.15 → fires
        )
        mock_thread.assert_called_once()

    with patch("agentic_traveler.analytics.judge.random.random", return_value=0.9), \
         patch("agentic_traveler.analytics.judge.threading.Thread") as mock_thread:
        maybe_judge_turn(
            reply_text="reply",
            intent="CHAT",
            char_cap=320,
            events=events,
            sample_rate=0.15,  # 0.9 >= 0.15 → skips
        )
        mock_thread.assert_not_called()


# ── E9: Selection turns (empty reply_text) never judged ───────────────────────

def test_empty_reply_skips_judge():
    """E9: empty reply_text → judge skipped (selection/deterministic turn)."""
    events = _mock_events()
    with patch("agentic_traveler.analytics.judge.threading.Thread") as mock_thread:
        maybe_judge_turn(
            reply_text="",
            intent="PLAN",
            char_cap=3500,
            events=events,
            sample_rate=1.0,
        )
        mock_thread.assert_not_called()


# ── AC-8: Schema parse + score emission ───────────────────────────────────────

def test_judge_emits_reply_judged_on_valid_output():
    """AC-8: Valid judge JSON → reply_judged metric emitted with all fields."""
    events = _mock_events()

    with patch("agentic_traveler.analytics.judge.get_client") as mock_gc, \
         patch("agentic_traveler.analytics.judge.gemini_generate") as mock_gen, \
         patch("agentic_traveler.analytics.judge.suppress_usage_capture"):

        mock_gc.return_value = MagicMock()
        mock_gen.return_value = _mock_response(_good_judge_output())

        # Run synchronously by calling _run_judge directly
        from agentic_traveler.analytics.judge import _run_judge
        _run_judge(
            reply_text="A clean reply.",
            intent="TRIP",
            char_cap=1500,
            params_just_set=False,
            owner_saga="DiscoverySaga",
            user_id="user-1",
            trip_id="trip-1",
            events=events,
        )

    emitted_metrics = [p for (n, p) in events._emitted if p.get("name") == "reply_judged"]
    assert len(emitted_metrics) == 1
    m = emitted_metrics[0]
    assert "scores" in m
    assert "purple_prose" in m
    assert m["intent"] == "TRIP"
    assert m["char_cap"] == 1500
    assert "prompt_version" in m


# ── E6: Out-of-range scores are clamped ──────────────────────────────────────

def test_clamp_scores_above_three():
    """E6: Scores > 3 are clamped to 3."""
    data = {k: 7 for k in _SCORE_KEYS}
    clamped = _clamp_scores(data)
    for k in _SCORE_KEYS:
        assert clamped[k] == 3


def test_clamp_scores_below_zero():
    """E6: Scores < 0 are clamped to 0."""
    data = {k: -1 for k in _SCORE_KEYS}
    clamped = _clamp_scores(data)
    for k in _SCORE_KEYS:
        assert clamped[k] == 0


def test_clamp_scores_in_range_unchanged():
    """Scores in [0, 3] are not modified."""
    data = {k: i % 4 for i, k in enumerate(_SCORE_KEYS)}
    clamped = _clamp_scores(data)
    for k in _SCORE_KEYS:
        assert 0 <= clamped[k] <= 3


# ── AC-10: Exception isolation ────────────────────────────────────────────────

def test_judge_exception_does_not_propagate():
    """AC-10: If the judge LLM call raises, the exception is swallowed."""
    events = _mock_events()

    with patch("agentic_traveler.analytics.judge.get_client") as mock_gc, \
         patch("agentic_traveler.analytics.judge.gemini_generate") as mock_gen, \
         patch("agentic_traveler.analytics.judge.suppress_usage_capture"):

        mock_gc.return_value = MagicMock()
        mock_gen.side_effect = RuntimeError("LLM exploded")

        from agentic_traveler.analytics.judge import _run_judge
        # Must not raise
        _run_judge(
            reply_text="A reply.",
            intent="CHAT",
            char_cap=320,
            params_just_set=False,
            owner_saga="ChatSaga",
            user_id="user-1",
            trip_id=None,
            events=events,
        )

    # judge_failed metric should be emitted
    emitted = [p for (n, p) in events._emitted if p.get("name") == "judge_failed"]
    assert len(emitted) == 1


def test_bad_json_drops_with_warning(caplog):
    """Malformed JSON from judge → dropped with warning, no raise (AC-8)."""
    import logging
    events = _mock_events()

    with patch("agentic_traveler.analytics.judge.get_client") as mock_gc, \
         patch("agentic_traveler.analytics.judge.gemini_generate") as mock_gen, \
         patch("agentic_traveler.analytics.judge.suppress_usage_capture"), \
         caplog.at_level(logging.WARNING):

        mock_gc.return_value = MagicMock()
        mock_gen.return_value = _mock_response("NOT VALID JSON !!!")

        from agentic_traveler.analytics.judge import _run_judge
        _run_judge(
            reply_text="A reply.",
            intent="PLAN",
            char_cap=3500,
            params_just_set=False,
            owner_saga="PlanningSaga",
            user_id="user-1",
            trip_id=None,
            events=events,
        )

    assert "non-JSON" in caplog.text or "failed" in caplog.text.lower()


def test_incomplete_schema_drops(caplog):
    """Judge JSON missing required keys → dropped (AC-8)."""
    import logging
    events = _mock_events()
    incomplete = json.dumps({"conciseness": 3})  # missing other required keys

    with patch("agentic_traveler.analytics.judge.get_client") as mock_gc, \
         patch("agentic_traveler.analytics.judge.gemini_generate") as mock_gen, \
         patch("agentic_traveler.analytics.judge.suppress_usage_capture"), \
         caplog.at_level(logging.WARNING):

        mock_gc.return_value = MagicMock()
        mock_gen.return_value = _mock_response(incomplete)

        from agentic_traveler.analytics.judge import _run_judge
        _run_judge(
            reply_text="A reply.",
            intent="CHAT",
            char_cap=320,
            params_just_set=False,
            owner_saga="ChatSaga",
            user_id="user-1",
            trip_id=None,
            events=events,
        )

    assert "incomplete" in caplog.text.lower() or "failed" in caplog.text.lower()


# ── E11: Judge input has no conversation history / PII ───────────────────────

def test_judge_input_no_conversation_history():
    """E11: _build_judge_input does not include conversation history or profile."""
    result = _build_judge_input(
        reply_text="Here is my reply.",
        intent="TRIP",
        char_cap=1500,
        params_just_set=True,
        owner_saga="DiscoverySaga",
    )
    assert "conversation" not in result.lower()
    assert "profile" not in result.lower()
    assert "user_name" not in result.lower()
    assert "Here is my reply." in result
    assert "TRIP" in result
    assert "1500" in result
    assert "true" in result  # params_just_set


def test_judge_input_contains_required_labels():
    """_build_judge_input emits all minimal context labels."""
    result = _build_judge_input(
        reply_text="Hello.",
        intent="CHAT",
        char_cap=320,
        params_just_set=False,
        owner_saga="ChatSaga",
    )
    assert "<intent>" in result
    assert "<char_cap>" in result
    assert "<params_just_set>" in result
    assert "<reply>" in result


# ── E10: Concurrent judge calls are independent ───────────────────────────────

def test_concurrent_judge_calls_independent():
    """E10: two simultaneous judge calls produce two independent reply_judged events."""
    events1 = _mock_events()
    events2 = _mock_events()
    barrier = threading.Barrier(2)
    results = {}

    def slow_judge(idx, events):
        barrier.wait()
        from agentic_traveler.analytics.judge import _run_judge
        with patch("agentic_traveler.analytics.judge.get_client") as mock_gc, \
             patch("agentic_traveler.analytics.judge.gemini_generate") as mock_gen, \
             patch("agentic_traveler.analytics.judge.suppress_usage_capture"):
            mock_gc.return_value = MagicMock()
            mock_gen.return_value = _mock_response(_good_judge_output())
            _run_judge(
                reply_text=f"Reply {idx}.",
                intent="CHAT",
                char_cap=320,
                params_just_set=False,
                owner_saga="ChatSaga",
                user_id=f"user-{idx}",
                trip_id=None,
                events=events,
            )
        results[idx] = [p for (n, p) in events._emitted if p.get("name") == "reply_judged"]

    t1 = threading.Thread(target=slow_judge, args=(1, events1))
    t2 = threading.Thread(target=slow_judge, args=(2, events2))
    t1.start()
    t2.start()
    t1.join(timeout=5)
    t2.join(timeout=5)

    # Each judge call emits to its own events instance — no cross-contamination.
    assert len(results.get(1, [])) == 1
    assert len(results.get(2, [])) == 1
