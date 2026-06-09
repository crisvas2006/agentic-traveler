"""Streaming generation wrapper — `generate_maybe_stream` (Task 37 + fixes).

Covers the empty-synthesis fallback that prevents the "I had trouble coming up
with a response" crash: when streaming + automatic function calling fires a tool
but streams back no synthesis text, the wrapper must fall back to a single
blocking call (which runs AFC reliably) and still surface the recovered answer
to the client. No real LLM — a fake client drives both code paths.
"""

from types import SimpleNamespace
from typing import Optional
from unittest.mock import patch

from agentic_traveler.orchestrator.client_factory import generate_maybe_stream
from agentic_traveler.orchestrator.event_emitter import EventEmitter


class _Chunk:
    """A streamed chunk. ``text`` may be falsy (function-call / usage-only)."""

    def __init__(self, text: Optional[str]):
        self.text = text


class _RaisingChunk:
    """A chunk whose ``.text`` raises — mirrors the SDK property blowing up on a
    non-text part (e.g. a function_call mid-stream)."""

    @property
    def text(self):
        raise ValueError("part is a function_call, not text")


class _Resp:
    def __init__(self, text: str):
        self.text = text


class _FakeModels:
    def __init__(self, stream_chunks, blocking_text):
        self._stream_chunks = stream_chunks
        self._blocking_text = blocking_text
        self.stream_calls = 0
        self.blocking_calls = 0

    def generate_content_stream(self, model, contents, config=None):
        self.stream_calls += 1
        yield from self._stream_chunks

    def generate_content(self, model, contents, config=None):
        self.blocking_calls += 1
        return _Resp(self._blocking_text)


class _FakeClient:
    def __init__(self, stream_chunks, blocking_text=""):
        self.models = _FakeModels(stream_chunks, blocking_text)


def _streaming_events():
    """An EventEmitter whose ``is_streaming`` is True (on_delta is wired)."""
    deltas: list[str] = []
    ee = EventEmitter(
        user_id="u1", trip_id=None,
        on_delta=lambda payload: deltas.append(payload["text"]),
    )
    return ee, deltas


def test_empty_streamed_synthesis_falls_back_to_blocking():
    # Stream yields only non-text chunks (the AFC tool-call turn) → empty text.
    client = _FakeClient(
        stream_chunks=[_Chunk(None), _Chunk("")],
        blocking_text="The weather in Mouscron is mild and cloudy.",
    )
    ee, deltas = _streaming_events()

    resp, text = generate_maybe_stream(client, "gemini-3.5-flash", "hi", None, ee)

    assert text == "The weather in Mouscron is mild and cloudy."
    assert client.models.stream_calls == 1
    assert client.models.blocking_calls == 1  # fell back
    # The recovered answer is pushed to the client as a single delta so the UI
    # still renders it (nothing was streamed before the fallback).
    assert deltas == ["The weather in Mouscron is mild and cloudy."]


def test_streamed_text_does_not_fall_back():
    client = _FakeClient(
        stream_chunks=[_Chunk("Hello "), _Chunk("there!")],
        blocking_text="SHOULD NOT BE USED",
    )
    ee, deltas = _streaming_events()

    resp, text = generate_maybe_stream(client, "gemini-3.5-flash", "hi", None, ee)

    assert text == "Hello there!"
    assert client.models.blocking_calls == 0  # no fallback when synthesis streamed
    assert deltas == ["Hello ", "there!"]


def test_raising_chunk_text_is_skipped_not_fatal():
    # A chunk whose `.text` raises must not abort the stream.
    client = _FakeClient(
        stream_chunks=[_RaisingChunk(), _Chunk("usable text")],
        blocking_text="SHOULD NOT BE USED",
    )
    ee, deltas = _streaming_events()

    resp, text = generate_maybe_stream(client, "gemini-3.5-flash", "hi", None, ee)

    assert text == "usable text"
    assert client.models.blocking_calls == 0
    assert deltas == ["usable text"]


def test_non_streaming_path_uses_blocking_call():
    # events=None → not streaming → single blocking call, no stream.
    client = _FakeClient(stream_chunks=[_Chunk("nope")], blocking_text="blocking answer")

    resp, text = generate_maybe_stream(client, "gemini-3.5-flash", "hi", None, None)

    assert text == "blocking answer"
    assert client.models.stream_calls == 0
    assert client.models.blocking_calls == 1


def test_fallback_still_empty_returns_empty():
    # Both paths empty (e.g. a genuine safety block) → empty text, no delta,
    # no crash. The orchestrator maps this to its ERROR fallback + records it.
    client = _FakeClient(stream_chunks=[_Chunk(None)], blocking_text="")
    ee, deltas = _streaming_events()

    resp, text = generate_maybe_stream(client, "gemini-3.5-flash", "hi", None, ee)

    assert text == ""
    assert client.models.blocking_calls == 1
    assert deltas == []


# ── tool-capable turns: blocking generation, then paced emit ───────────────

_TOOL_CONFIG = SimpleNamespace(tools=[lambda: None])  # any truthy tools list


def test_tool_turn_uses_blocking_and_paces_the_reply():
    # With tools present, streaming + AFC is unreliable on Vertex, so we generate
    # in ONE blocking call and pace the answer to the client as multiple deltas.
    answer = "Saturday morning, wander the old town; afternoon, a quiet museum."
    client = _FakeClient(stream_chunks=[_Chunk("SHOULD NOT STREAM")], blocking_text=answer)
    ee, deltas = _streaming_events()

    with patch("agentic_traveler.orchestrator.client_factory.time.sleep"):
        resp, text = generate_maybe_stream(client, "gemini-3.5-flash", "hi", _TOOL_CONFIG, ee)

    assert text == answer
    assert client.models.stream_calls == 0     # never used the flaky streaming path
    assert client.models.blocking_calls == 1   # one reliable generation, no double cost
    assert len(deltas) > 1                      # paced into multiple chunks
    assert "".join(deltas) == answer            # chunks reconstruct the answer exactly


def test_tool_turn_empty_reply_emits_nothing():
    client = _FakeClient(stream_chunks=[], blocking_text="")
    ee, deltas = _streaming_events()

    with patch("agentic_traveler.orchestrator.client_factory.time.sleep"):
        resp, text = generate_maybe_stream(client, "gemini-3.5-flash", "hi", _TOOL_CONFIG, ee)

    assert text == ""
    assert deltas == []


def test_tool_turn_non_streaming_is_plain_blocking():
    # Telegram / no delta sink → blocking, no pacing, no deltas.
    client = _FakeClient(stream_chunks=[], blocking_text="A reply.")

    resp, text = generate_maybe_stream(client, "gemini-3.5-flash", "hi", _TOOL_CONFIG, None)

    assert text == "A reply."
    assert client.models.blocking_calls == 1
