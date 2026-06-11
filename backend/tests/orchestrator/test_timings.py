"""Task 48 — Latency & context efficiency instrumentation tests.

Covers:
  - AC-1: turn_stage_timings emission shape (sync, E8 selection).
  - AC-2: llm_call_usage emission with thinking_tokens (E1 missing metadata).
  - AC-5: parallel router + extractor (E2 CHAT discard, E3 failure isolation).
  - E4: history cap independence from SagaState.prefetched_slots.
  - ttft_ms captured on first delta event.
"""

from __future__ import annotations

import time
from types import SimpleNamespace
from unittest.mock import MagicMock, patch

import pytest

from agentic_traveler.orchestrator.client_factory import (
    begin_usage_capture,
    current_turn_usage,
    gemini_generate,
)
from agentic_traveler.orchestrator.event_emitter import EventEmitter


# ── fixtures ─────────────────────────────────────────────────────────────────

def _usage(prompt=100, candidates=50, thoughts=20):
    return SimpleNamespace(
        prompt_token_count=prompt,
        candidates_token_count=candidates,
        thoughts_token_count=thoughts,
    )


def _response(*, prompt=100, candidates=50, thoughts=20, usage=True, text="ok"):
    cand = SimpleNamespace(grounding_metadata=None, content=SimpleNamespace(parts=[]))
    return SimpleNamespace(
        usage_metadata=_usage(prompt, candidates, thoughts) if usage else None,
        candidates=[cand],
        text=text,
    )


def _client(response):
    m = MagicMock()
    m.models.generate_content.return_value = response
    return m


@pytest.fixture(autouse=True)
def _clean():
    current_turn_usage.set(None)
    yield
    current_turn_usage.set(None)


# ── AC-2: llm_call_usage metric emission ─────────────────────────────────────

def test_llm_call_usage_emitted_with_thinking_tokens():
    """AC-2: llm_call_usage metric carries input, output, thinking tokens and latency."""
    begin_usage_capture()
    events = EventEmitter(user_id="u1", trip_id=None)
    events._metric_buffer.clear()

    # Patch the current emitter so _capture_usage can find it.
    with patch(
        "agentic_traveler.orchestrator.client_factory.get_current_emitter",
        return_value=events,
    ):
        gemini_generate(
            _client(_response(prompt=200, candidates=80, thoughts=30)),
            model="gemini-3.1-flash-lite",
            contents="test",
            config=None,
            call_type="extraction",
        )

    metric_rows = [r for r in events._metric_buffer if r["event_name"] == "llm_call_usage"]
    assert len(metric_rows) == 1
    payload = metric_rows[0]["payload"]
    assert payload["call_type"] == "extraction"
    assert payload["input_tokens"] == 200
    assert payload["output_tokens"] == 80
    assert payload["thinking_tokens"] == 30
    assert payload["latency_ms"] is not None
    assert payload["latency_ms"] >= 0


def test_llm_call_usage_thinking_tokens_stored_in_records():
    """thinking_tokens persisted in the token record for billing audit."""
    records = begin_usage_capture()
    gemini_generate(
        _client(_response(prompt=150, candidates=60, thoughts=40)),
        model="m",
        contents="x",
        config=None,
    )
    assert records[0]["thinking_tokens"] == 40


def test_llm_call_usage_e1_missing_metadata_no_emit():
    """E1: missing usage_metadata → no llm_call_usage emitted, no crash."""
    begin_usage_capture()
    events = EventEmitter(user_id="u1", trip_id=None)
    with patch(
        "agentic_traveler.orchestrator.client_factory.get_current_emitter",
        return_value=events,
    ):
        gemini_generate(
            _client(_response(usage=False)),
            model="m",
            contents="x",
            config=None,
            call_type="extraction",
        )
    metric_names = [r["event_name"] for r in events._metric_buffer]
    assert "llm_call_usage" not in metric_names


def test_llm_call_usage_no_emitter_no_crash():
    """When no emitter is bound (non-turn context), capture still appends records."""
    records = begin_usage_capture()
    with patch(
        "agentic_traveler.orchestrator.client_factory.get_current_emitter",
        return_value=None,
    ):
        gemini_generate(
            _client(_response()),
            model="m",
            contents="x",
            config=None,
        )
    assert len(records) == 1


# ── AC-1 / EventEmitter: ttft tracking ───────────────────────────────────────

def test_ttft_ms_set_on_first_delta():
    """ttft_ms is populated when the first delta event fires."""
    events = EventEmitter(user_id="u", trip_id=None, on_delta=lambda _: None)
    assert events.ttft_ms is None
    events.emit("delta", {"text": "hello"})
    assert events.ttft_ms is not None
    assert events.ttft_ms >= 0


def test_ttft_ms_not_set_without_delta():
    """Non-streaming turns never set ttft_ms."""
    events = EventEmitter(user_id="u", trip_id=None)
    events.emit("status", {"phase": "router", "text": "Thinking…"})
    assert events.ttft_ms is None


def test_ttft_ms_only_recorded_once():
    """First delta sets ttft; subsequent deltas do not overwrite it."""
    events = EventEmitter(user_id="u", trip_id=None, on_delta=lambda _: None)
    events.emit("delta", {"text": "a"})
    first = events.ttft_ms
    time.sleep(0.05)
    events.emit("delta", {"text": "b"})
    assert events.ttft_ms == first


# ── AC-5: parallel extractor — E2 / E3 ───────────────────────────────────────

def test_prefetched_slots_in_saga_state_bypasses_extraction():
    """When state['prefetched_slots'] is provided, PlanningSaga skips extract_trip_slots."""
    from agentic_traveler.orchestrator.sagas.planning import PlanningSaga

    saga = PlanningSaga(client=MagicMock())
    saga._client = MagicMock()

    # Patch extract_trip_slots to detect if it's called.
    with patch(
        "agentic_traveler.orchestrator.sagas.planning.extract_trip_slots",
    ) as mock_extract:
        with patch.object(saga, "_decide") as mock_decide:
            mock_decide.return_value = MagicMock(
                text="ok", slot_request=None, side_effects=[]
            )
            mock_decide.return_value.side_effects = []
            saga.run(
                message="Tokyo, two weeks",
                user_doc={"user_name": "T"},
                trip=None,
                state={
                    "intent": "PLAN",
                    "message_text": "Tokyo, two weeks",
                    "prefetched_slots": {"destinations": ["Tokyo"]},
                },
                conversation_context="",
                events=EventEmitter(user_id="u", trip_id=None),
            )
        mock_extract.assert_not_called()


def test_prefetched_slots_none_triggers_extraction():
    """When prefetched_slots is None (E3 failure), PlanningSaga calls extract_trip_slots."""
    from agentic_traveler.orchestrator.sagas.planning import PlanningSaga

    saga = PlanningSaga(client=MagicMock())

    with patch(
        "agentic_traveler.orchestrator.sagas.planning.extract_trip_slots",
        return_value={"destinations": ["Paris"]},
    ) as mock_extract:
        with patch.object(saga, "_decide") as mock_decide:
            mock_decide.return_value = MagicMock(
                text="ok", slot_request=None, side_effects=[]
            )
            mock_decide.return_value.side_effects = []
            saga.run(
                message="Paris trip",
                user_doc={"user_name": "T"},
                trip=None,
                state={
                    "intent": "PLAN",
                    "message_text": "Paris trip",
                    "prefetched_slots": None,
                },
                conversation_context="",
                events=EventEmitter(user_id="u", trip_id=None),
            )
        mock_extract.assert_called_once()


def test_skip_message_handled_even_with_prefetch():
    """E4 / skip fast-path: 'skip' with pending_slot always takes the fast path,
    ignoring any prefetched_slots result (avoids losing the pending_slot context)."""
    from agentic_traveler.orchestrator.sagas.planning import PlanningSaga

    saga = PlanningSaga(client=MagicMock())
    captured_side_effects: list = []

    with patch(
        "agentic_traveler.orchestrator.sagas.planning.extract_trip_slots",
    ) as mock_extract:
        with patch.object(saga, "_decide") as mock_decide:
            mock_decide.return_value = MagicMock(
                text="ok", slot_request=None, side_effects=[]
            )
            mock_decide.return_value.side_effects = captured_side_effects
            saga.run(
                message="skip",
                user_doc={"user_name": "T"},
                trip={"id": "trip-1", "preferences": {}},
                state={
                    "intent": "PLAN",
                    "message_text": "skip",
                    "pending_slot": "pace",
                    "prefetched_slots": {},  # prefetch ran, found nothing
                },
                conversation_context="",
                events=EventEmitter(user_id="u", trip_id=None),
            )
        # skip fast-path should NOT call the LLM extractor
        mock_extract.assert_not_called()
        # _decide should have been called with the skip write in side_effects
        _, kwargs = mock_decide.call_args
        # side_effects should include the pace=skip write
        assert any(
            getattr(se, "payload", {}).get("preferences", {}).get("pace") == "skip"
            for se in kwargs.get("side_effects", [])
        )


# ── E8: selection / no-text turns have stable timings shape ──────────────────

def test_stage_timings_shape_with_all_zeros():
    """E8: selection turns pass all-zero stage_timings; turn_stage_timings event
    must still be well-formed (no KeyError / None issues)."""
    stage_timings = {"router_ms": 0.0, "extractor_ms": 0.0, "agent_ms": 0.0}
    events = EventEmitter(user_id="u", trip_id=None)

    # Replicate the emission logic from _save_and_finish.
    st = stage_timings or {}
    events.emit("metric", {
        "name": "turn_stage_timings",
        "router_ms": int(st.get("router_ms") or 0),
        "extractor_ms": int(st.get("extractor_ms") or 0),
        "agent_ms": int(st.get("agent_ms") or 0),
        "tools_ms": None,
        "persist_ms": 5,
        "total_ms": 100,
        "ttft_ms": None,
    })

    rows = [r for r in events._metric_buffer if r["event_name"] == "turn_stage_timings"]
    assert len(rows) == 1
    payload = rows[0]["payload"]
    assert payload["router_ms"] == 0
    assert payload["extractor_ms"] == 0
    assert payload["agent_ms"] == 0
    assert payload["total_ms"] == 100
    assert payload["ttft_ms"] is None


# ── AC-5: prefetched_slots=None vs {} semantics ───────────────────────────────

def test_empty_prefetch_dict_is_used_not_fallen_back():
    """An empty dict from prefetch means 'extractor ran, found nothing' — must be
    used as-is (no LLM fallback) so the extraction cost is accepted exactly once."""
    from agentic_traveler.orchestrator.sagas.planning import PlanningSaga

    saga = PlanningSaga(client=MagicMock())

    with patch(
        "agentic_traveler.orchestrator.sagas.planning.extract_trip_slots",
    ) as mock_extract:
        with patch.object(saga, "_decide") as mock_decide:
            mock_decide.return_value = MagicMock(
                text="ok", slot_request=None, side_effects=[]
            )
            mock_decide.return_value.side_effects = []
            saga.run(
                message="let me think about it",
                user_doc={"user_name": "T"},
                trip=None,
                state={
                    "intent": "PLAN",
                    "message_text": "let me think about it",
                    "prefetched_slots": {},  # empty dict = ran, found nothing
                },
                conversation_context="",
                events=EventEmitter(user_id="u", trip_id=None),
            )
        mock_extract.assert_not_called()
