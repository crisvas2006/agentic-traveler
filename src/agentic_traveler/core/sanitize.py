"""
Input sanitization for user messages before LLM prompt injection.

Strips potentially dangerous control characters while preserving
normal text content. Applied once at the webhook entry point so
all downstream agents receive clean input.
"""

import logging
import re

logger = logging.getLogger(__name__)

# Control chars (U+0000–U+001F, U+007F–U+009F) except common whitespace
_CONTROL_CHAR_RE = re.compile(
    r"[\x00-\x08\x0b\x0c\x0e-\x1f\x7f-\x9f]"
)


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
