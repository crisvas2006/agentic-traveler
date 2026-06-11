"""
Unit tests for two pure helpers introduced in task_54:

- client_factory._trace_inputs / _summarize_config — the LangSmith
  process_inputs reducer that makes a GenerateContentConfig carrying Python
  function tools serializable (the original failure was
  PydanticSerializationError: Unable to serialize unknown type <class 'function'>).
- budget_policy.resolve — maps call_type + reply_length_preference to a
  Budget (Task 47 replacement for the removed trip_agent._length_guidance).

No Gemini/network calls — these are pure functions.
"""

import json

from google.genai import types

from agentic_traveler.orchestrator.client_factory import (
    _summarize_config,
    _trace_inputs,
)
from agentic_traveler.core.budget_policy import resolve as budget_resolve, SCALING


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


# ── budget_policy.resolve (replaces _length_guidance from task_54) ─────────────
# Task 47: _length_guidance and _LENGTH_GUIDANCE were removed from trip_agent.py
# and replaced by the centralised BudgetPolicy. These tests verify the same
# product invariants (explicit prefs respected, unknown → default, conciseness
# is the default product stance) using the new module.

def _doc(pref):
    """Minimal user_doc with a reply_length_preference (or none if pref is None)."""
    profile_data = {} if pref is None else {"reply_length_preference": pref}
    return {"user_profile": {"profile_data": profile_data}}


def test_budget_resolve_explicit_preferences_scale_correctly():
    """Terse < default < verbose for trip_companion char_cap."""
    terse = budget_resolve("trip_companion", _doc("terse")).char_cap
    default = budget_resolve("trip_companion", _doc("default")).char_cap
    verbose = budget_resolve("trip_companion", _doc("verbose")).char_cap
    assert terse < default < verbose


def test_budget_resolve_is_case_insensitive():
    """Preference matching is case-insensitive."""
    upper = budget_resolve("chat_ack", _doc("TERSE")).char_cap
    lower = budget_resolve("chat_ack", _doc("terse")).char_cap
    assert upper == lower


def test_budget_resolve_defaults_to_default_when_unset_or_unknown():
    """Unset or unknown preference → default scaling (x1.0)."""
    default = budget_resolve("chat_ack", _doc("default")).char_cap
    assert budget_resolve("chat_ack", _doc(None)).char_cap == default
    assert budget_resolve("chat_ack", _doc("rambling")).char_cap == default
    assert budget_resolve("chat_ack", {}).char_cap == default
    assert budget_resolve("chat_ack", {"user_profile": None}).char_cap == default


def test_default_scaling_signals_conciseness():
    """Guard product invariant: default scale is 1.0 (not inflated toward verbose)."""
    assert SCALING["default"] == 1.0, "Default must not inflate reply length"
    assert SCALING["terse"] < 1.0, "Terse must be shorter than default"
    assert SCALING["verbose"] > 1.0, "Verbose must be longer than default"
