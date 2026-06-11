"""
Unit tests for core/budget_policy.py (Task 47 AC-1/2/3/5, E2/E3/E4/E5).

No Gemini calls — pure logic only.
"""

import pytest
from types import SimpleNamespace

from agentic_traveler.core.budget_policy import (
    BUDGETS,
    CHAR_FLOOR,
    Budget,
    build_voice_block,
    handle_finish_reason,
    resolve,
    trim_to_budget,
)


# ── Fixtures ─────────────────────────────────────────────────────────────────

def _user_doc(pref: str | None = None) -> dict:
    """Build a minimal user_doc with the given reply_length_preference."""
    if pref is None:
        return {}
    return {"user_profile": {"profile_data": {"reply_length_preference": pref}}}


# ── AC-1: All call types resolve without error ────────────────────────────────

def test_all_call_types_resolve():
    """Every entry in BUDGETS resolves to a valid Budget."""
    for call_type in BUDGETS:
        b = resolve(call_type)
        assert isinstance(b, Budget), f"{call_type} did not return Budget"
        assert b.max_tokens_ceiling > 0
        assert b.thinking_level in ("LOW", "MEDIUM")


def test_unknown_call_type_falls_back_to_chat_ack():
    """Unknown call_type gracefully falls back to chat_ack defaults."""
    b = resolve("nonexistent_call_type")
    chat_ack_budget = resolve("chat_ack")
    assert b.max_tokens_ceiling == chat_ack_budget.max_tokens_ceiling


# ── AC-2: Budget table matches spec §7.1 exactly ─────────────────────────────

@pytest.mark.parametrize("call_type,expected_char,expected_level,expected_ceiling", [
    ("chat_ack",           320,   "LOW",    1280),
    ("slot_question",      200,   "LOW",    1216),
    ("advisor_turn",       350,   "LOW",    1280),
    ("orient_question",    200,   "LOW",    1216),
    ("suggestions",        1200,  "LOW",    1984),
    ("country_intel_line", 280,   "LOW",    1280),
    ("trip_companion",     1500,  "LOW",    2176),
    ("itinerary",          3500,  "MEDIUM", 6784),
    ("judge",              0,     "LOW",    1024),
    ("extraction",         0,     "LOW",    512),
])
def test_budget_table_exact_values(call_type, expected_char, expected_level, expected_ceiling):
    b = resolve(call_type)
    assert b.char_cap == expected_char, f"{call_type}: char_cap mismatch"
    assert b.thinking_level == expected_level, f"{call_type}: thinking_level mismatch"
    assert b.max_tokens_ceiling == expected_ceiling, f"{call_type}: ceiling mismatch"


# ── AC-2: reply_length_preference scaling ─────────────────────────────────────

def test_terse_scaling():
    """terse ×0.6 — floored at CHAR_FLOOR."""
    b = resolve("chat_ack", _user_doc("terse"))
    expected = max(int(320 * 0.6), CHAR_FLOOR)
    assert b.char_cap == expected


def test_verbose_scaling():
    """verbose ×2 — capped at CHAR_CAP_CEILING (3500)."""
    b = resolve("chat_ack", _user_doc("verbose"))
    expected = min(int(320 * 2.0), 3500)
    assert b.char_cap == expected


def test_verbose_scaling_itinerary_capped_at_ceiling():
    """verbose ×2 on itinerary (3500 base) stays ≤ CHAR_CAP_CEILING."""
    b = resolve("itinerary", _user_doc("verbose"))
    assert b.char_cap <= 3500


def test_default_scaling_unchanged():
    """default (×1.0) returns base char_cap."""
    b = resolve("chat_ack", _user_doc("default"))
    assert b.char_cap == 320


# ── AC-2: max_tokens_ceiling never altered by user pref ──────────────────────

def test_ceiling_unchanged_by_preference():
    """max_tokens_ceiling must be identical regardless of user preference."""
    base = resolve("trip_companion")
    terse = resolve("trip_companion", _user_doc("terse"))
    verbose = resolve("trip_companion", _user_doc("verbose"))
    assert terse.max_tokens_ceiling == base.max_tokens_ceiling
    assert verbose.max_tokens_ceiling == base.max_tokens_ceiling


# ── AC-3: thinking_level set per call type ───────────────────────────────────

def test_chat_ack_thinking_is_low():
    assert resolve("chat_ack").thinking_level == "LOW"


def test_itinerary_thinking_is_medium():
    assert resolve("itinerary").thinking_level == "MEDIUM"


def test_thinking_budget_low():
    b = resolve("chat_ack")
    assert b.thinking_budget == 256


def test_thinking_budget_medium():
    b = resolve("itinerary")
    assert b.thinking_budget == 4096


# ── E4: Unknown preference → default (×1) ────────────────────────────────────

def test_unknown_preference_defaults_to_one():
    """E4: unknown preference value → default scaling."""
    b = resolve("chat_ack", _user_doc("superfast"))
    assert b.char_cap == 320  # default scaling × 1.0


# ── E5: Terse scaling below CHAR_FLOOR → floored ─────────────────────────────

def test_terse_floor_enforced():
    """E5: terse scaling on small char_cap is floored at CHAR_FLOOR."""
    # slot_question base=200, terse=200*0.6=120 → exactly at floor
    b = resolve("slot_question", _user_doc("terse"))
    assert b.char_cap >= CHAR_FLOOR


def test_floor_at_exactly_char_floor():
    """No pref should push char_cap below CHAR_FLOOR."""
    for call_type in BUDGETS:
        for pref in ("terse", "default", "verbose"):
            b = resolve(call_type, _user_doc(pref))
            if b.char_cap > 0:  # skip zero-cap types (judge, extraction)
                assert b.char_cap >= CHAR_FLOOR, \
                    f"{call_type}/{pref}: char_cap={b.char_cap} below CHAR_FLOOR={CHAR_FLOOR}"


# ── Zero-cap call types (judge, extraction) ───────────────────────────────────

def test_zero_cap_types_not_scaled():
    """Judge and extraction have zero char_cap and should not be scaled."""
    for pref in ("terse", "default", "verbose"):
        bj = resolve("judge", _user_doc(pref))
        be = resolve("extraction", _user_doc(pref))
        assert bj.char_cap == 0
        assert be.char_cap == 0


# ── trim_to_budget ────────────────────────────────────────────────────────────

def test_trim_exact_cap_no_trim():
    """E2: text exactly at cap → no trim."""
    text = "x" * 100
    result, was_trimmed = trim_to_budget(text, 100)
    assert result == text
    assert was_trimmed is False


def test_trim_under_cap_no_trim():
    text = "Hello world."
    result, was_trimmed = trim_to_budget(text, 200)
    assert result == text
    assert was_trimmed is False


def test_trim_within_15pct_trims_at_sentence():
    """Reply over cap by ≤15% is trimmed at sentence boundary."""
    text = "First sentence. Second sentence here."
    cap = len("First sentence.") + 2  # within 15%: len(text) ≈ 37, cap ≈ 17
    # 15% of 17 = 2.55, 37-17=20 > 15%, so this is actually >15%... pick valid case.
    # Let's use text where overage is <15%:
    text = "First sentence. Second."
    cap = int(len(text) * 0.92)  # 8% under → overage is ~9%
    result, was_trimmed = trim_to_budget(text, cap)
    assert was_trimmed is True
    assert len(result) <= cap or result.endswith(".")


def test_trim_over_15pct_returned_as_is():
    """AC-5: reply over cap by >15% is returned as-is (budget_violation signal)."""
    text = "A" * 200
    cap = 100  # 100% overage
    result, was_trimmed = trim_to_budget(text, cap)
    assert result == text  # returned as-is
    assert was_trimmed is True


def test_trim_zero_cap_no_op():
    """Zero cap = no-op (judge and extraction call types)."""
    text = "Some text here."
    result, was_trimmed = trim_to_budget(text, 0)
    assert result == text
    assert was_trimmed is False


def test_trim_unicode_safe():
    """Unicode characters (emoji, accents) do not cause index errors."""
    text = "Héllo wörld! 🌍 This is a long reply with emoji."
    result, was_trimmed = trim_to_budget(text, 30)
    # Should not raise; result should be a valid unicode substring
    assert isinstance(result, str)


def test_trim_does_not_split_link():
    """E3: Trim backs off before an unclosed [link] construct."""
    # Text is 10% over cap — within the ≤15% trim-eligible window.
    # The trim should land before the '[' open bracket.
    sentence = "Good sentence. "
    link_fragment = "[and this is a long link"
    text = sentence + link_fragment
    # cap is ~10% under len(text) → within 15% window → trim should fire
    cap = int(len(text) * 0.92)
    result, was_trimmed = trim_to_budget(text, cap)
    # The result must not end with an unclosed '['
    # Either the link part was trimmed (result ends at sentence boundary before '[')
    # or a word boundary before it was used.
    assert "[" not in result, (
        f"Trim left unclosed '[' in: {result!r}"
    )


def test_trim_does_not_split_bold():
    """E3: Trim backs off before an unclosed **bold** span."""
    # Text is ~8% over cap — within the ≤15% trim-eligible window.
    sentence = "Good info here. "
    bold_fragment = "**this is bold span"
    text = sentence + bold_fragment
    cap = int(len(text) * 0.92)
    result, was_trimmed = trim_to_budget(text, cap)
    # The result must not contain an unclosed '**'
    bold_count = result.count("**")
    assert bold_count % 2 == 0, (
        f"Unclosed **bold** in trimmed result: {result!r}"
    )


# ── handle_finish_reason ──────────────────────────────────────────────────────

def _mock_response(finish_reason_name: str, text: str = "Some text."):
    candidate = SimpleNamespace(
        finish_reason=SimpleNamespace(name=finish_reason_name)
    )
    response = SimpleNamespace(candidates=[candidate], text=text)
    return response


def test_handle_finish_reason_normal():
    """Non-MAX_TOKENS finish → text unchanged, ceiling_hit=False."""
    resp = _mock_response("STOP", "A great reply.")
    text, ceiling_hit = handle_finish_reason(resp, "A great reply.", "chat_ack")
    assert ceiling_hit is False
    assert text == "A great reply."


def test_handle_finish_reason_max_tokens_with_sentences():
    """AC-4: MAX_TOKENS + complete sentences → salvaged text."""
    long_text = "First sentence. Second sentence. Truncated mid-word trun"
    resp = _mock_response("MAX_TOKENS", long_text)
    text, ceiling_hit = handle_finish_reason(resp, long_text, "trip_companion")
    assert ceiling_hit is True
    assert text  # something was salvaged
    assert text.endswith(".")


def test_handle_finish_reason_max_tokens_no_sentences():
    """E1: MAX_TOKENS + zero complete sentences → empty text (friendly retry path)."""
    partial = "Incomplete text without any sentence ender"
    resp = _mock_response("MAX_TOKENS", partial)
    text, ceiling_hit = handle_finish_reason(resp, partial, "itinerary")
    assert ceiling_hit is True
    assert text == ""  # caller uses friendly retry


def test_handle_finish_reason_no_candidates():
    """No candidates → text unchanged, ceiling_hit=False."""
    resp = SimpleNamespace(candidates=[], text="x")
    text, ceiling_hit = handle_finish_reason(resp, "x", "chat_ack")
    assert ceiling_hit is False


def test_handle_finish_reason_none_response():
    """None response → no crash, text returned as-is."""
    text, ceiling_hit = handle_finish_reason(None, "original", "chat_ack")
    assert ceiling_hit is False
    assert text == "original"


# ── Voice block ───────────────────────────────────────────────────────────────

def test_voice_block_contains_char_cap():
    """build_voice_block injects the char_cap value."""
    block = build_voice_block(1500)
    assert "1500" in block


def test_voice_block_contains_bad_examples():
    """AC-6: Both verbatim BAD examples from §7.2 are present."""
    block = build_voice_block(320)
    assert "unadulterated quiet" in block, "First BAD example missing"
    assert "high-vibe energy" in block, "Second BAD example missing"


def test_voice_block_contains_hard_wall_rule():
    """Voice block includes the 'hard wall' budget instruction."""
    block = build_voice_block(320)
    assert "hard wall" in block
