"""
Unit tests for two pure helpers introduced in task_54:

- client_factory._trace_inputs / _summarize_config — the LangSmith
  process_inputs reducer that makes a GenerateContentConfig carrying Python
  function tools serializable (the original failure was
  PydanticSerializationError: Unable to serialize unknown type <class 'function'>).
- trip_agent._length_guidance — maps reply_length_preference to a directive,
  defaulting to the concise "default" setting.

No Gemini/network calls — these are pure functions.
"""

import json

from google.genai import types

from agentic_traveler.orchestrator.client_factory import (
    _summarize_config,
    _trace_inputs,
)
from agentic_traveler.orchestrator.trip_agent import _LENGTH_GUIDANCE, _length_guidance


def _dummy_tool(location: str, days: int) -> str:
    """A stand-in tool function (same shape as check_weather)."""
    return ""


# ── _trace_inputs / _summarize_config ────────────────────────────────────────

def test_trace_inputs_with_function_tool_is_json_serializable():
    """The exact regression: a config with a function tool must serialize, and
    tools must be reduced to their names."""
    cfg = types.GenerateContentConfig(
        max_output_tokens=800,
        thinking_config=types.ThinkingConfig(thinking_budget=256),
        tools=[_dummy_tool],
    )
    inputs = {
        "client": object(),  # unserializable; must be dropped
        "model": "gemini-3.5-flash",
        "contents": "hello prompt",
        "config": cfg,
    }

    safe = _trace_inputs(inputs)

    # client dropped, model + contents kept
    assert "client" not in safe
    assert safe["model"] == "gemini-3.5-flash"
    assert safe["contents"] == "hello prompt"

    # config reduced to a serializable summary; tools are NAME strings
    assert safe["config"]["tools"] == ["_dummy_tool"]
    assert safe["config"]["max_output_tokens"] == 800
    assert safe["config"]["thinking_budget"] == 256

    # the whole payload must round-trip through JSON (what LangSmith does)
    json.dumps(safe)


def test_summarize_config_none_returns_none():
    assert _summarize_config(None) is None


def test_summarize_config_without_tools_omits_tools_key():
    """Router/chat configs carry no tools — the key should simply be absent."""
    cfg = types.GenerateContentConfig(
        max_output_tokens=400,
        response_mime_type="application/json",
    )
    summary = _summarize_config(cfg)
    assert "tools" not in summary
    assert summary["max_output_tokens"] == 400
    assert summary["response_mime_type"] == "application/json"
    json.dumps(summary)


def test_summarize_config_non_function_tool_uses_type_name():
    """A non-function tool (e.g. a google_search grounding Tool) falls back to
    its type name rather than raising."""
    grounding_tool = types.Tool(google_search=types.GoogleSearch())
    cfg = types.GenerateContentConfig(tools=[grounding_tool])
    summary = _summarize_config(cfg)
    assert summary["tools"] == ["Tool"]
    json.dumps(summary)


def test_trace_inputs_without_config_key_is_safe():
    safe = _trace_inputs({"client": object(), "model": "m", "contents": "c"})
    assert "client" not in safe
    assert safe == {"model": "m", "contents": "c"}


# ── _length_guidance ─────────────────────────────────────────────────────────

def _doc(pref):
    """Minimal user_doc with a reply_length_preference (or none if pref is None)."""
    profile_data = {} if pref is None else {"reply_length_preference": pref}
    return {"user_profile": {"profile_data": profile_data}}


def test_length_guidance_explicit_preferences():
    assert _length_guidance(_doc("terse")) == _LENGTH_GUIDANCE["terse"]
    assert _length_guidance(_doc("default")) == _LENGTH_GUIDANCE["default"]
    assert _length_guidance(_doc("verbose")) == _LENGTH_GUIDANCE["verbose"]


def test_length_guidance_is_case_insensitive():
    assert _length_guidance(_doc("TERSE")) == _LENGTH_GUIDANCE["terse"]
    assert _length_guidance(_doc("Verbose")) == _LENGTH_GUIDANCE["verbose"]


def test_length_guidance_defaults_to_concise_when_unset_or_unknown():
    # unset preference
    assert _length_guidance(_doc(None)) == _LENGTH_GUIDANCE["default"]
    # unknown value
    assert _length_guidance(_doc("rambling")) == _LENGTH_GUIDANCE["default"]
    # missing user_profile / profile_data entirely
    assert _length_guidance({}) == _LENGTH_GUIDANCE["default"]
    assert _length_guidance({"user_profile": None}) == _LENGTH_GUIDANCE["default"]


def test_default_guidance_signals_conciseness():
    """Guard the product invariant: the default directive must push for brevity."""
    assert "CONCISE" in _LENGTH_GUIDANCE["default"]
    assert "VERY BRIEF" in _LENGTH_GUIDANCE["terse"]
