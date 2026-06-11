"""Canonical Markdown profile for Aletheia agents (task 46).

``CANONICAL_FORMATTING`` is a single shared instruction block imported by every
agent that produces user-visible text.  It replaces the old per-agent Telegram
formatting sections, which carried channel-specific rules (*bold* was
Telegram-MarkdownV1 that the web renderer misread as italic).

``degrade_for_telegram`` converts canonical Markdown → Telegram MarkdownV1.
It is called in the channel layer (telegram.py) *before* the existing
``sanitize_telegram_markdown`` call so degradation precedes chunking (E11).

All rules are idempotent: running the function twice on the same input
produces the same output as running it once (E6, AC-8).
"""

from __future__ import annotations

import logging
import re

logger = logging.getLogger(__name__)

# ── Canonical formatting block (imported by every agent) ────────────────────

CANONICAL_FORMATTING = """\
FORMATTING (canonical — identical on every device and channel):
- Plain conversational paragraphs by default; Markdown only where it helps.
- **bold** for place names and key facts; *italics* sparingly.
- "- " bullet lists or "1. " numbered lists for options/steps, one line each.
- Exactly one heading level: "### " before day/section titles
  (e.g. "### Day 2 — Taormina"). Never # or ##, never deeper structure.
- "> " blockquote for short callouts: tips, caveats, and the
  verify-with-official-sources disclaimer.
- [text](url) links when citing sources.
- NEVER: tables, code blocks, images, HTML, nested lists.
- Must read perfectly on a small phone screen: short paragraphs
  (≤ 3 sentences), short lines, no wall-of-text.
"""

# ── Telegram degrader (standard Markdown → MarkdownV1) ──────────────────────

# Compiled patterns — ordered so headings are processed before bold (which uses
# the same asterisk delimiter) and bold before sanitization.

# §### Heading (any depth) → *Title*  (E2: all depths normalized)
_RE_HEADING = re.compile(r"^#{1,6}\s+(.*)", re.MULTILINE)

# **bold** → *bold*  (capture group avoids double-degradation because the
# output uses single asterisks which this pattern never matches again — E6)
_RE_BOLD = re.compile(r"\*\*(.+?)\*\*")

# > blockquote (contiguous lines collected as one block) → _text_  (E5)
# Processed line-by-line: each "> " line is converted independently;
# the Telegram client renders them as italic, which is the best V1 equivalent.
_RE_BLOCKQUOTE_LINE = re.compile(r"^>\s*(.*)", re.MULTILINE)

# "- item" / "* item" bullet → "• item"
_RE_BULLET = re.compile(r"^[-*]\s+", re.MULTILINE)

# Table rows: | cell | cell | → cells joined with " — "
# (E1: agent may emit a table; we flatten rather than reject)
_RE_TABLE_ROW = re.compile(r"^\|(.+)\|$", re.MULTILINE)
_RE_TABLE_SEP = re.compile(r"^\|[-| :]+\|$", re.MULTILINE)

# Code fence opening/closing lines (``` or ~~~) → removed; content kept (E1)
_RE_CODE_FENCE = re.compile(r"^(`{3,}|~{3,}).*", re.MULTILINE)

# Observe violations (tables, code) for the `markdown_profile_violation` metric.
_RE_VIOLATION_TABLE = re.compile(r"^\|.+\|", re.MULTILINE)
_RE_VIOLATION_CODE = re.compile(r"^(`{3}|~{3})", re.MULTILINE)


def _emit_violation(kind: str) -> None:
    """Log a structured metric when an agent emits a forbidden element."""
    logger.warning(
        "markdown_profile_violation element=%s", kind,
        extra={"metric": "markdown_profile_violation", "element": kind},
    )


def degrade_for_telegram(text: str) -> str:
    """Convert canonical Markdown → Telegram MarkdownV1.

    Deterministic and idempotent (running twice = running once, E6/AC-8).
    Processes in order:
      1. Code fences removed (content kept).
      2. Table separator rows removed; data rows flattened to "cell — cell".
      3. Headings (all depths) → *Title*.
      4. **bold** → *bold*.
      5. > blockquote lines → _quote_.
      6. Bullet "- item" / "* item" → "• item".
      7. Links preserved ([text](url) is valid V1).
    """
    if not text:
        return text

    # Observe forbidden elements before stripping them.
    if _RE_VIOLATION_TABLE.search(text):
        _emit_violation("table")
    if _RE_VIOLATION_CODE.search(text):
        _emit_violation("code_fence")

    # 1. Code fence delimiters removed (keep the content between them).
    text = _RE_CODE_FENCE.sub("", text)

    # 2. Table rows: separator → remove; data → flatten.
    text = _RE_TABLE_SEP.sub("", text)
    text = _RE_TABLE_ROW.sub(
        lambda m: " — ".join(
            cell.strip() for cell in m.group(1).split("|") if cell.strip()
        ),
        text,
    )

    # 3. Headings (all depths) → *Title*  (E2).
    text = _RE_HEADING.sub(lambda m: f"*{m.group(1).strip()}*", text)

    # 4. **bold** → *bold*  (idempotent: output is single-asterisk).
    text = _RE_BOLD.sub(lambda m: f"*{m.group(1)}*", text)

    # 5. > blockquote → _quote_
    text = _RE_BLOCKQUOTE_LINE.sub(lambda m: f"_{m.group(1).strip()}_", text)

    # 6. Bullet → •
    text = _RE_BULLET.sub("• ", text)

    # Collapse runs of blank lines left by removed elements.
    text = re.sub(r"\n{3,}", "\n\n", text)

    return text.strip()
