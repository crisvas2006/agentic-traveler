"""True token streaming + tool-status plumbing (Task 37).

Covers `generate_maybe_stream` (stream vs sync), and the `emit_tool_status`
contextvar mechanism the tools use. No real Gemini / DB.
"""

from types import SimpleNamespace

from agentic_traveler.orchestrator.client_factory import generate_maybe_stream
from agentic_traveler.orchestrator.event_emitter import EventEmitter
from agentic_traveler.orchestrator.tool_events import (
    emit_tool_status,
    reset_current_emitter,
    set_current_emitter,
)


class _StreamClient:
    """Minimal stand-in for genai.Client.models with both call shapes."""

    def __init__(self, chunks, sync_text="sync reply"):
        self.models = SimpleNamespace(
            generate_content_stream=lambda model, contents, config: iter(chunks),
            generate_content=lambda model, contents, config: SimpleNamespace(text=sync_text),
        )


# ---------------------------------------------------------------------------
# generate_maybe_stream
# ---------------------------------------------------------------------------

def test_streams_deltas_when_streaming():
    chunks = [
        SimpleNamespace(text="Iceland in "),
        SimpleNamespace(text="late January"),
        SimpleNamespace(text=None),   # non-text chunk (e.g. tool step) → skipped
    ]
    deltas = []
    events = EventEmitter(user_id="u", trip_id=None, on_delta=lambda p: deltas.append(p["text"]))
    resp, text = generate_maybe_stream(_StreamClient(chunks), "m", "contents", None, events)
    assert text == "Iceland in late January"
    assert deltas == ["Iceland in ", "late January"]


def test_single_call_when_not_streaming():
    events = EventEmitter(user_id="u", trip_id=None)  # no on_delta → not streaming
    resp, text = generate_maybe_stream(
        _StreamClient([SimpleNamespace(text="ignored")], sync_text="Sync reply"),
        "m", "contents", None, events,
    )
    assert text == "Sync reply"


def test_no_events_uses_sync_path():
    resp, text = generate_maybe_stream(
        _StreamClient([], sync_text="Sync reply"), "m", "contents", None, None
    )
    assert text == "Sync reply"


def test_tool_status_emitted_during_stream():
    """A tool invoked mid-stream can emit status via the bound emitter — this is
    how 'Checking the weather…' reaches the user during generation."""
    statuses = []
    events = EventEmitter(
        user_id="u", trip_id=None,
        on_status=lambda p: statuses.append(p),
        on_delta=lambda p: None,
    )

    def stream(model, contents, config):
        emit_tool_status("check_weather")   # SDK invokes the tool mid-stream
        yield SimpleNamespace(text="...forecast-informed reply...")

    client = SimpleNamespace(models=SimpleNamespace(generate_content_stream=stream))
    generate_maybe_stream(client, "m", "contents", None, events)
    assert any(s.get("phase") == "tool" and s.get("tool") == "check_weather" for s in statuses)


# ---------------------------------------------------------------------------
# emit_tool_status contextvar
# ---------------------------------------------------------------------------

def test_emit_tool_status_when_bound():
    statuses = []
    events = EventEmitter(user_id="u", trip_id=None, on_status=lambda p: statuses.append(p))
    token = set_current_emitter(events)
    try:
        emit_tool_status("check_weather")
    finally:
        reset_current_emitter(token)
    assert len(statuses) == 1
    assert statuses[0]["phase"] == "tool"
    assert "weather" in statuses[0]["text"].lower()


def test_emit_tool_status_noop_when_unbound():
    emit_tool_status("check_weather")  # no emitter bound → must not raise


def test_emit_tool_status_silent_for_unmapped_tool():
    statuses = []
    events = EventEmitter(user_id="u", trip_id=None, on_status=lambda p: statuses.append(p))
    token = set_current_emitter(events)
    try:
        emit_tool_status("not_a_real_tool")
    finally:
        reset_current_emitter(token)
    assert statuses == []
