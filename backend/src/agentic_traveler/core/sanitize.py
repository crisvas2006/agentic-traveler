"""
Input sanitization utilities.

sanitize_user_input  — strips control characters from raw user messages
                       before they reach any LLM prompt.
sanitize_telegram_markdown — fixes unbalanced Markdown entities in LLM
                             output before it is sent to Telegram, preventing
                             400 "Can't find end of the entity" errors.
"""

import logging
import re

logger = logging.getLogger(__name__)

# Control chars (U+0000–U+001F, U+007F–U+009F) except common whitespace
_CONTROL_CHAR_RE = re.compile(
    r"[\x00-\x08\x0b\x0c\x0e-\x1f\x7f-\x9f]"
)


def sanitize_telegram_markdown(text: str) -> str:
    """
    Fix unbalanced Telegram MarkdownV1 entities in LLM output before sending.

    Telegram MarkdownV1 uses *text* for bold and _text_ for italic.
    An unmatched delimiter (e.g. "5* hotel", a trailing asterisk) causes
    a 400 "Can't find end of the entity" error and the message is never sent.

    Strategy:
    1. Convert star-rating patterns like "5*" / "4 * property" to "5★"
       (Unicode BLACK STAR is safe and visually equivalent).
    2. If * count is still odd after step 1, strip bare asterisks that are
       not part of a *word* bold pair until the count is even.
    3. Same treatment for _ (italic).
    """
    if not text:
        return text

    # Step 1 — star ratings: "5* hotel", "4*", "a 3 * room" → "5★ hotel"
    text = re.sub(r"(\d)\s*\*", r"\1★", text)

    # Step 2 — balance remaining *
    # A "bare" asterisk is one that is NOT immediately adjacent to a non-space
    # character on both sides (i.e. not part of *bold text*).
    while text.count("*") % 2 != 0:
        # Prefer to remove a bare * (surrounded by spaces / at boundary)
        m = re.search(r"(?<![^\s])\*|(?<!\*)\*(?![^\s])", text)
        if m:
            text = text[: m.start()] + text[m.end() :]
        else:
            # All remaining * are word-adjacent; remove the last one
            pos = text.rfind("*")
            if pos == -1:
                break
            text = text[:pos] + text[pos + 1 :]
            logger.debug("sanitize_telegram_markdown: removed orphan * at pos %d", pos)

    # Step 3 — balance remaining _
    while text.count("_") % 2 != 0:
        m = re.search(r"(?<![^\s])_|(?<!_)_(?![^\s])", text)
        if m:
            text = text[: m.start()] + text[m.end() :]
        else:
            pos = text.rfind("_")
            if pos == -1:
                break
            text = text[:pos] + text[pos + 1 :]
            logger.debug("sanitize_telegram_markdown: removed orphan _ at pos %d", pos)

    return text


def sanitize_user_input(text: str) -> str:
    """
    Clean user input before it reaches any LLM prompt.

    - Strips null bytes and control characters (preserves newlines,
      tabs, and carriage returns).
    - Strips leading/trailing whitespace.

    Args:
        text: Raw user message from Telegram.

    Returns:
        Sanitized text ready for prompt inclusion.
    """
    if not text:
        return ""

    cleaned = _CONTROL_CHAR_RE.sub("", text)
    cleaned = cleaned.strip()

    if len(cleaned) != len(text.strip()):
        logger.warning(
            "Sanitized input: removed %d control characters.",
            len(text.strip()) - len(cleaned),
        )

    return cleaned
