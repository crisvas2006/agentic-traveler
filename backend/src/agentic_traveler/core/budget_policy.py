"""
Reply-length budget policy (Task 47).

Single source of truth for all LLM call token limits, thinking levels,
and character caps. Every agent and saga resolves its generation config
through here — no scattered ``max_output_tokens`` literals.

Key design decisions:
- ``max_tokens_ceiling`` is a SAFETY ceiling (cost + infinite-thinking guard),
  NOT a style lever. On Gemini 3.x, it caps thinking + visible output combined.
  Tightening it to force brevity silently starves visible output. Don't do that.
- Voice discipline = prompt-layer (ANTI_BLOAT_VOICE_BLOCK) + deterministic trim.
- ``thinking_level`` maps to the thinking_budget kwarg: LOW=256, MEDIUM=4096.
  Conversational calls use LOW; planner uses MEDIUM.
- ``reply_length_preference`` scaling only affects ``char_cap`` — it never
  raises ``max_tokens_ceiling``.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Any, Dict, Optional

# ── Budget table ────────────────────────────────────────────────────────────
# call_type            char_cap  thinking_level  max_tokens_ceiling
# Ceiling formula: tokens ≈ chars/4 → ceiling = 3×(chars/4) + thinking headroom
#                  thinking headroom: +1024 LOW / +4096 MEDIUM
BUDGETS: Dict[str, tuple[int, str, int]] = {
    "chat_ack":           (320,   "LOW",    1280),
    "slot_question":      (200,   "LOW",    1216),
    "advisor_turn":       (350,   "LOW",    1280),   # task 45 composer
    "orient_question":    (200,   "LOW",    1216),
    "suggestions":        (1200,  "LOW",    1984),
    "country_intel_line": (280,   "LOW",    1280),
    "trip_companion":     (1500,  "LOW",    2176),   # TripAgent default
    "itinerary":          (3500,  "MEDIUM", 6784),   # PlannerAgent
    "judge":              (0,     "LOW",    1024),   # structured output
    "extraction":         (0,     "LOW",    512),    # slot/booking extractors
}

# Scaling factors for reply_length_preference — char_cap ONLY.
SCALING: Dict[str, float] = {
    "terse":   0.6,
    "default": 1.0,
    "verbose": 2.0,
}

# Floor: even "terse" must fit one useful sentence.
CHAR_FLOOR = 120

# Ceiling for scaled char_cap (itinerary base is the max sensible reply).
CHAR_CAP_CEILING = 3500

# Thinking budget tokens per level.
_THINKING_BUDGETS: Dict[str, int] = {
    "LOW":    256,
    "MEDIUM": 4096,
}


# ── Budget dataclass ─────────────────────────────────────────────────────────

@dataclass
class Budget:
    """Resolved per-call token budget."""
    char_cap: int           # Max visible characters (style constraint)
    thinking_level: str     # "LOW" | "MEDIUM"
    max_tokens_ceiling: int  # Hard SDK ceiling (cost + hang guard)

    @property
    def thinking_budget(self) -> int:
        """Tokens to allocate for thinking."""
        return _THINKING_BUDGETS.get(self.thinking_level, 256)


# ── Resolver ────────────────────────────────────────────────────────────────

def resolve(call_type: str, user_doc: Optional[Dict[str, Any]] = None) -> Budget:
    """Resolve the Budget for *call_type* scaled by the user's length preference.

    Layering order (fixed per spec §5):
      1. System default from BUDGETS table.
      2. Scaled by ``profile_data.reply_length_preference``.
      3. Floor at CHAR_FLOOR; ceiling at CHAR_CAP_CEILING.
      4. max_tokens_ceiling is NEVER altered by user preference.

    Unknown call_type falls back to "chat_ack".
    """
    base_char, thinking_level, ceiling = BUDGETS.get(call_type, BUDGETS["chat_ack"])

    # Zero-cap call types (judge, extraction) skip scaling entirely.
    if base_char == 0:
        return Budget(
            char_cap=0,
            thinking_level=thinking_level,
            max_tokens_ceiling=ceiling,
        )

    # Derive preference from user_doc.
    profile_data = (
        ((user_doc or {}).get("user_profile") or {}).get("profile_data") or {}
    )
    pref = ((profile_data.get("reply_length_preference") or "default")).lower().strip()
    scale = SCALING.get(pref, SCALING["default"])  # E4: unknown → default

    scaled = int(base_char * scale)
    scaled = max(scaled, CHAR_FLOOR)           # E5: floor
    scaled = min(scaled, CHAR_CAP_CEILING)     # ceiling

    return Budget(
        char_cap=scaled,
        thinking_level=thinking_level,
        max_tokens_ceiling=ceiling,
    )


# ── Trim helper ─────────────────────────────────────────────────────────────

# Patterns for inline markdown constructs that must not be trimmed mid-span.
# We back off to the sentence boundary *before* any open construct.
_MARKDOWN_OPEN = re.compile(
    r"\[(?=[^\]]*$)"           # unclosed [link text
    r"|\*\*(?=[^*]*$)"        # unclosed **bold
    r"|(?<!\*)\*(?!\*)(?=[^*]*$)"  # unclosed *italic
    r"|`(?=[^`]*$)",           # unclosed `code
    re.UNICODE,
)


def trim_to_budget(text: str, cap: int) -> tuple[str, bool]:
    """Trim *text* to at most *cap* characters, respecting sentence boundaries
    and markdown constructs (E3).

    Returns ``(trimmed_text, was_trimmed)``.

    Rules (AC-5):
    - Exactly at cap → (text, False).
    - Over by ≤15%  → trim at last sentence boundary under cap.
    - Over by >15%  → return as-is; caller emits ``budget_violation`` metric.
      (The judge's raw signal — we don't silently truncate long replies.)
    - Trim never splits inside a [link](url) or **bold** span.
    """
    if cap <= 0:
        return text, False
    text = (text or "").strip()
    if len(text) <= cap:
        return text, False

    overage_pct = (len(text) - cap) / cap * 100
    if overage_pct > 15:
        # Over by >15% → send as-is; caller records budget_violation metric.
        return text, True

    # Trim: find last sentence boundary at or before cap, avoiding open markdown spans.
    window = text[:cap]

    # Reject a trim point if it lands inside an open markdown construct.
    def _safe_trim(pos: int) -> bool:
        snippet = window[:pos]
        return _MARKDOWN_OPEN.search(snippet) is None

    # Walk sentence terminators backwards.
    for pattern in (r"[.!?]\s", r"[.!?]$"):
        for m in reversed(list(re.finditer(pattern, window))):
            end = m.start() + 1
            if _safe_trim(end):
                return window[:end].strip(), True

    # Fallback: word boundary.
    space = window.rfind(" ")
    if space > 0 and _safe_trim(space):
        return window[:space].rstrip(), True

    return window.rstrip(), True


# ── Anti-bloat voice block ────────────────────────────────────────────────────

# §7.2 verbatim — injected into every agent system prompt with {char_cap} filled.
# The block replaces all per-agent length wording (TripAgent's _LENGTH_GUIDANCE,
# PlannerAgent's "STRICT LENGTH LIMIT", ChatAgent's equivalents).
_VOICE_BLOCK_TEMPLATE = """\
VOICE — read carefully, these are hard rules:
- Lead with the substance. No warm-up sentences, no "Great question!",
  no scene-setting preamble.
- You know this traveler. SHOW it through apt choices; NEVER tell it.
  Telling is forbidden. Two real failures you must never reproduce:
    BAD: "When you drop the dollar sign, we both know we're talking
         top-shelf, high-roller territory—pure, unadulterated quiet
         luxury where the doors open before you even have to knock."
         (narrating the user's preference back at them)
    BAD: "For a medium-paced, loose-structured Italian escape with that
         effortless, high-vibe energy, we are heading straight to…"
         (restating parameters the user picked seconds ago)
  At most ONE quietly fitting adjective carries the personalization.
- Never restate trip parameters the user just set. Use them silently.
- Offer 2-3 pointed options and stop; the user will ask for more.
- Your reply budget is {char_cap} characters. Treat it as a hard wall:
  finish your last sentence well before it.
"""

_PROMPT_VERSION = "voice_block.v1"


def build_voice_block(char_cap: int) -> str:
    """Return the §7.2 anti-bloat voice block with *char_cap* substituted."""
    return _VOICE_BLOCK_TEMPLATE.format(char_cap=char_cap)


# ── Finish-reason handler ────────────────────────────────────────────────────

def handle_finish_reason(
    response: Any,
    text: str,
    call_type: str,
) -> tuple[str, bool]:
    """Inspect *response* for a MAX_TOKENS finish reason (AC-4).

    Returns ``(final_text, ceiling_hit)`` where:
    - ceiling_hit=True → caller should emit ``token_ceiling_hit`` metric.
    - If ceiling was hit and text has ≥1 complete sentence, the text is
      salvaged (sentence-trimmed). Otherwise the caller should serve the
      existing friendly-retry message.

    Never raises. Returns the original text unchanged on any error.
    """
    try:
        candidates = getattr(response, "candidates", None)
        if not candidates:
            return text, False
        finish = getattr(candidates[0], "finish_reason", None)
        # Gemini SDK uses FinishReason enum; compare by name for portability.
        finish_name = getattr(finish, "name", str(finish))
        if finish_name not in ("MAX_TOKENS", "2"):  # 2 = MAX_TOKENS numeric value
            return text, False
    except Exception:
        return text, False

    # Ceiling was hit. Attempt to salvage the last complete sentence.
    if not text:
        return text, True

    sentence_end = max(
        text.rfind(". "), text.rfind("! "), text.rfind("? "),
        text.rfind(".\n"), text.rfind("!\n"), text.rfind("?\n"),
    )
    if sentence_end > 0:
        salvaged = text[: sentence_end + 1].strip()
        return salvaged, True

    # No complete sentence salvageable → caller uses friendly-retry.
    return "", True
