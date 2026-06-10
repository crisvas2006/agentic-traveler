"""Task 51 — global LLM cost deduction.

The `gemini_generate` / `gemini_generate_stream` funnel appends every call's
token usage to a per-turn ContextVar (`current_turn_usage`) so the
orchestrator can bill the user for ALL LLM work in the turn — including
nested tools (booking_parser) that never surface a raw response upward.
"""

import contextvars
import threading
from types import SimpleNamespace
from unittest.mock import MagicMock, patch

import pytest

from agentic_traveler.orchestrator.client_factory import (
    begin_usage_capture,
    current_turn_usage,
    gemini_generate,
    gemini_generate_stream,
    suppress_usage_capture,
)


def _usage(prompt=120, candidates=60):
    return SimpleNamespace(prompt_token_count=prompt, candidates_token_count=candidates)


def _response(*, prompt=120, candidates=60, usage=True, grounded=False, text="hello"):
    cand = SimpleNamespace(
        grounding_metadata=(
            SimpleNamespace(grounding_chunks=["chunk"]) if grounded else None
        ),
        content=SimpleNamespace(parts=[]),
    )
    return SimpleNamespace(
        usage_metadata=_usage(prompt, candidates) if usage else None,
        candidates=[cand],
        text=text,
    )


def _client(response):
    client = MagicMock()
    client.models.generate_content.return_value = response
    return client


@pytest.fixture(autouse=True)
def _clean_context():
    """Tests in this module share one thread context — start each with no
    active capture, exactly like a fresh worker thread."""
    current_turn_usage.set(None)
    yield
    current_turn_usage.set(None)


# ── capture basics ───────────────────────────────────────────────────────────

def test_capture_appends_record_when_turn_active():
    records = begin_usage_capture()
    gemini_generate(
        _client(_response()), model="gemini-3.1-flash-lite", contents="x", config=None
    )
    assert records == [{
        "model_name": "gemini-3.1-flash-lite",
        "input_tokens": 120,
        "output_tokens": 60,
        "total_tokens": 180,
    }]


def test_no_capture_without_active_turn():
    """Default context (scripts, webhooks, background work) → silent no-op."""
    gemini_generate(
        _client(_response()), model="gemini-3.1-flash-lite", contents="x", config=None
    )
    assert current_turn_usage.get() is None


def test_failed_call_appends_nothing():
    records = begin_usage_capture()
    client = MagicMock()
    client.models.generate_content.side_effect = RuntimeError("boom")
    with pytest.raises(RuntimeError):
        gemini_generate(client, model="m", contents="x", config=None)
    assert records == []


def test_missing_usage_metadata_appends_nothing():
    records = begin_usage_capture()
    gemini_generate(_client(_response(usage=False)), model="m", contents="x", config=None)
    assert records == []


def test_grounded_response_appends_grounding_record():
    records = begin_usage_capture()
    gemini_generate(
        _client(_response(grounded=True)), model="gemini-3.1-flash-lite",
        contents="x", config=None,
    )
    assert len(records) == 2
    grounding = records[1]
    assert grounding["model_name"] == "grounding"
    assert grounding["grounding_cost_credits"] >= 1
    assert grounding["total_tokens"] == 0


def test_stream_captures_usage_from_last_chunk():
    records = begin_usage_capture()
    first = _response(usage=False, text="Hel")
    last = _response(prompt=200, candidates=80, text="lo")
    client = MagicMock()
    client.models.generate_content_stream.return_value = iter([first, last])
    resp, text = gemini_generate_stream(client, model="m", contents="x", config=None)
    assert text == "Hello"
    assert resp is last
    assert records == [{
        "model_name": "m",
        "input_tokens": 200,
        "output_tokens": 80,
        "total_tokens": 280,
    }]


# ── lifecycle: begin / suppress / reset ──────────────────────────────────────

def test_begin_resets_previous_turn_records():
    """A reused worker thread must never leak records across turns."""
    stale = begin_usage_capture()
    gemini_generate(_client(_response()), model="m", contents="x", config=None)
    fresh = begin_usage_capture()
    assert fresh == []
    assert fresh is not stale
    gemini_generate(_client(_response()), model="m", contents="x", config=None)
    assert len(fresh) == 1
    assert len(stale) == 1  # untouched after the reset


def test_suppress_usage_capture_excludes_system_calls():
    """Self-billing / platform-overhead calls (compaction, future judge) must
    not enter the user's deduction."""
    records = begin_usage_capture()
    with suppress_usage_capture():
        gemini_generate(_client(_response()), model="m", contents="x", config=None)
    assert records == []
    gemini_generate(_client(_response()), model="m", contents="x", config=None)
    assert len(records) == 1  # capture resumes after the block


# ── threading semantics (task 48 alignment note) ─────────────────────────────

def test_copied_context_in_thread_appends_to_same_list():
    """`contextvars.copy_context().run(...)` in a worker thread shares the
    SAME list object — parallel calls (task 48) stay billable."""
    records = begin_usage_capture()
    ctx = contextvars.copy_context()

    def _call():
        gemini_generate(_client(_response()), model="m", contents="x", config=None)

    t = threading.Thread(target=ctx.run, args=(_call,))
    t.start()
    t.join()
    assert len(records) == 1


def test_plain_thread_does_not_capture():
    """Raw Thread/pool submission without copy_context sees no active turn —
    the documented hazard: it must no-op, never crash or cross-bill."""
    records = begin_usage_capture()

    def _call():
        gemini_generate(_client(_response()), model="m", contents="x", config=None)

    t = threading.Thread(target=_call)
    t.start()
    t.join()
    assert records == []


# ── exclusions and inclusions at the call sites ──────────────────────────────

def test_compaction_summarise_is_not_billed_to_user():
    from agentic_traveler.orchestrator.conversation_manager import ConversationManager

    records = begin_usage_capture()
    manager = ConversationManager(client=_client(_response(text="summary")))
    with patch(
        "agentic_traveler.orchestrator.conversation_manager.usage_tracker"
    ):
        out = manager._summarise([{"role": "user", "text": "hi"}], "")
    assert out == "summary"
    assert records == []


def test_booking_parser_usage_is_captured():
    """AC-3: the nested booking extraction call lands in the turn's records."""
    from agentic_traveler.tools import booking_parser

    records = begin_usage_capture()
    response = _response(
        prompt=300, candidates=40,
        text='{"booking_kind": "flight", "confidence": 0.9}',
    )
    with patch.object(booking_parser, "get_client", return_value=_client(response)):
        extraction, raw = booking_parser.parse_booking("WZZ 1234 OTP-CTA")
    assert extraction.booking_kind == "flight"
    assert raw is response
    assert records == [{
        "model_name": "gemini-3.1-flash-lite",
        "input_tokens": 300,
        "output_tokens": 40,
        "total_tokens": 340,
    }]
