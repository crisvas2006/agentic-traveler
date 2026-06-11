"""Unit tests for core/markdown_profile.py (Task 46).

Covers:
  - Every degrade_for_telegram rule (AC-8).
  - Idempotency: running twice = running once (E6 / AC-8).
  - Table flattening (E1).
  - Heading depth normalization (E2).
  - Multi-line blockquote (E5).
  - Code fence stripping (E1 variant).
  - CANONICAL_FORMATTING present in agent system prompts (AC-7).
  - No "Telegram" formatting directives in agent system prompts (AC-7).
"""

import pytest

from agentic_traveler.core.markdown_profile import (
    CANONICAL_FORMATTING,
    degrade_for_telegram,
)


# ── degrade_for_telegram rules (AC-8) ─────────────────────────────────────────

class TestDegradeHeadings:
    """AC-8 / E2: ### Title → *Title*; all heading depths normalize."""

    def test_h3_heading(self):
        assert degrade_for_telegram("### Day 2 — Taormina") == "*Day 2 — Taormina*"

    def test_h1_heading(self):
        assert degrade_for_telegram("# Title") == "*Title*"

    def test_h2_heading(self):
        assert degrade_for_telegram("## Section") == "*Section*"

    def test_h4_heading(self):
        assert degrade_for_telegram("#### Sub") == "*Sub*"

    def test_heading_in_body(self):
        result = degrade_for_telegram("Intro\n\n### Day 1\n\nContent")
        assert "*Day 1*" in result
        assert "###" not in result


class TestDegradeBold:
    """AC-8: **bold** → *bold*"""

    def test_simple_bold(self):
        assert degrade_for_telegram("**Kyoto**") == "*Kyoto*"

    def test_bold_in_sentence(self):
        result = degrade_for_telegram("Visit **Isola Bella** at opening.")
        assert "*Isola Bella*" in result
        assert "**" not in result

    def test_multiple_bold(self):
        result = degrade_for_telegram("**a** and **b**")
        assert result == "*a* and *b*"


class TestDegradeBlockquote:
    """AC-8 / E5: > quote → _quote_; multi-line blockquote."""

    def test_single_line_quote(self):
        assert degrade_for_telegram("> Verify entry rules with official sources.") == (
            "_Verify entry rules with official sources._"
        )

    def test_multi_line_blockquote(self):
        # Each line converted independently; not per-line fragments
        text = "> Line one.\n> Line two."
        result = degrade_for_telegram(text)
        assert "_Line one._" in result
        assert "_Line two._" in result
        assert ">" not in result


class TestDegradeBullets:
    """AC-8: "- item" / "* item" → "• item"."""

    def test_dash_bullet(self):
        result = degrade_for_telegram("- Morning at the market")
        assert result == "• Morning at the market"

    def test_star_bullet(self):
        result = degrade_for_telegram("* Evening stroll")
        assert result == "• Evening stroll"

    def test_bullet_list(self):
        text = "- Item one\n- Item two"
        result = degrade_for_telegram(text)
        assert result == "• Item one\n• Item two"


class TestDegradeLinks:
    """AC-8: [text](url) links are preserved unchanged."""

    def test_link_preserved(self):
        src = "Check [official sources](https://example.com)"
        assert degrade_for_telegram(src) == src

    def test_link_in_body(self):
        src = "See [Rome guide](https://example.com) for details."
        result = degrade_for_telegram(src)
        assert "[Rome guide](https://example.com)" in result


class TestDegradeTable:
    """E1: Table rows flattened; separator rows removed."""

    def test_table_data_row_flattened(self):
        result = degrade_for_telegram("| City | Days |\n| Rome | 3 |")
        assert "|" not in result
        assert "City" in result
        assert "Days" in result

    def test_table_separator_removed(self):
        result = degrade_for_telegram("| col |\n|---|\n| val |")
        assert "|" not in result
        assert "---" not in result
        assert "val" in result


class TestDegradeCodeFence:
    """E1: Code fence delimiters stripped; content kept verbatim."""

    def test_code_fence_delimiters_removed(self):
        text = "```python\nprint('hi')\n```"
        result = degrade_for_telegram(text)
        assert "```" not in result
        assert "print('hi')" in result

    def test_tilde_fence(self):
        text = "~~~\nsome code\n~~~"
        result = degrade_for_telegram(text)
        assert "~~~" not in result
        assert "some code" in result


class TestDegradeIdempotency:
    """E6 / AC-8: Running degrade_for_telegram twice = running it once."""

    def test_heading_idempotent(self):
        src = "### Day 1"
        once = degrade_for_telegram(src)
        twice = degrade_for_telegram(once)
        assert once == twice

    def test_bold_idempotent(self):
        src = "**bold text**"
        once = degrade_for_telegram(src)
        twice = degrade_for_telegram(once)
        assert once == twice

    def test_blockquote_idempotent(self):
        src = "> Verify with official sources."
        once = degrade_for_telegram(src)
        twice = degrade_for_telegram(once)
        assert once == twice

    def test_bullet_idempotent(self):
        src = "- Item"
        once = degrade_for_telegram(src)
        twice = degrade_for_telegram(once)
        assert once == twice

    def test_full_fixture_idempotent(self):
        """Canonical sample fixture from spec §8 testing plan."""
        src = (
            "### Day 2 — Taormina\n"
            "- **Isola Bella** at opening\n\n"
            "> Verify entry rules with official sources"
        )
        once = degrade_for_telegram(src)
        twice = degrade_for_telegram(once)
        assert once == twice

    def test_link_idempotent(self):
        src = "[text](https://example.com)"
        once = degrade_for_telegram(src)
        twice = degrade_for_telegram(once)
        assert once == twice


class TestDegradeCanonicalFixture:
    """Spec §8 sample fixture: canonical → Telegram (AC-8 end-to-end)."""

    def test_full_fixture(self):
        src = (
            "### Day 2 — Taormina\n"
            "- **Isola Bella** at opening\n\n"
            "> Verify entry rules with official sources"
        )
        result = degrade_for_telegram(src)
        assert "*Day 2 — Taormina*" in result
        assert "• *Isola Bella* at opening" in result
        assert "_Verify entry rules with official sources_" in result


class TestDegradeEdgeCases:
    """Edge cases not covered above."""

    def test_empty_string(self):
        assert degrade_for_telegram("") == ""

    def test_plain_paragraph_unchanged(self):
        src = "Just a normal paragraph with no special formatting."
        assert degrade_for_telegram(src) == src

    def test_numbered_list_unchanged(self):
        """Numbered lists are preserved — MarkdownV1 supports them natively."""
        src = "1. First\n2. Second"
        assert degrade_for_telegram(src) == src


# ── AC-7: Canonical formatting constant + prompt assertions ──────────────────

class TestCanonicalFormattingConstant:
    """CANONICAL_FORMATTING is a non-empty string with the required markers."""

    def test_not_empty(self):
        assert len(CANONICAL_FORMATTING.strip()) > 50

    def test_contains_heading_rule(self):
        assert "###" in CANONICAL_FORMATTING

    def test_contains_bold_rule(self):
        assert "**bold**" in CANONICAL_FORMATTING

    def test_contains_blockquote_rule(self):
        assert '> "' in CANONICAL_FORMATTING or "> " in CANONICAL_FORMATTING

    def test_no_telegram_mention(self):
        """The constant itself must not mention Telegram (it is channel-agnostic)."""
        assert "Telegram" not in CANONICAL_FORMATTING


class TestAgentPromptsCanonical:
    """AC-7: Each agent system prompt contains CANONICAL_FORMATTING and has no
    Telegram-specific formatting directives."""

    def _prompts(self):
        """Collect all agent system prompts (import lazily to avoid heavy deps in test env)."""
        from agentic_traveler.orchestrator.trip_agent import _SYSTEM_PROMPT as trip
        from agentic_traveler.orchestrator.chat_agent import _SYSTEM_PROMPT as chat
        from agentic_traveler.orchestrator.planner_agent import _SYSTEM_PROMPT as planner
        from agentic_traveler.orchestrator.sagas.advisor_turn import _SYSTEM_PROMPT as advisor
        return {"trip": trip, "chat": chat, "planner": planner, "advisor": advisor}

    @pytest.mark.parametrize("name", ["trip", "chat", "planner", "advisor"])
    def test_canonical_formatting_present(self, name):
        prompts = self._prompts()
        # The constant text (first line) must appear verbatim in each prompt.
        canonical_first_line = CANONICAL_FORMATTING.splitlines()[0].strip()
        assert canonical_first_line in prompts[name], (
            f"{name} prompt missing CANONICAL_FORMATTING first line"
        )

    @pytest.mark.parametrize("name", ["trip", "chat", "planner", "advisor"])
    def test_no_telegram_formatting_directives(self, name):
        prompts = self._prompts()
        # "Formatting (Telegram)" or "Formatting:" with old Telegram-style rules
        # must no longer appear. We check for the specific old strings.
        forbidden = ["Formatting (Telegram)", "Do NOT use headers (#)"]
        for f in forbidden:
            assert f not in prompts[name], (
                f"{name} prompt still contains old Telegram directive: {f!r}"
            )
