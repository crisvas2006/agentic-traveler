"""CuriosityPromptInjector (task 42) — picks at most one literature-grounded
curiosity prompt to weave into an exploratory reply, and frames it so it lands
well *coming from an AI*.

Pure Python, no LLM. The prompt texts live in
``content/curiosity_prompts.yaml`` (human-curated, source-cited).

The "AI effect" problem & how this module answers it
----------------------------------------------------
A deep, open question that delights coming from a travel-loving friend
("what's the picture in your head when you imagine being there?") can fall
flat — even feel intrusive or performative — when an AI asks it cold. People
answer machines more tersely and are quick to ignore anything that reads like
a survey. Three guards, applied here:

1. **Tuned phrasing** — the library texts are concrete and low-effort
   (often a light either/or), answerable in a few words. The *literature*
   informs WHY we ask (the rationale cites the source); the wording is
   de-intellectualised.
2. **Optional-aside delivery** — ``frame_curiosity_prompt`` wraps the text in
   strict instructions: one short casual line at the END of an
   already-useful reply, never an interview, answerable-or-ignorable, never
   repeated, dropped if it would feel intrusive.
3. **Earned, not cold-open** — an entry can set ``requires_destination`` so
   the more personal prompts only fire once the user has shown some commitment
   (a destination on the trip), plus a once-per-day cap and a hard opt-out for
   high-structure planners.
"""

from __future__ import annotations

import hashlib
import logging
import os
from datetime import date
from pathlib import Path
from typing import Any, Optional

import yaml
from pydantic import BaseModel, Field

logger = logging.getLogger(__name__)

LIBRARY_PATH = Path(__file__).resolve().parent.parent / "content" / "curiosity_prompts.yaml"


# ── models ───────────────────────────────────────────────────────────────────

class CuriositySource(BaseModel):
    author: str
    title: str
    year: Optional[int] = None
    page: Optional[int] = None


class CuriosityTrigger(BaseModel):
    states: list[str]
    # Match if ANY listed motivation is present (profile travel_motivations or
    # the trip's discovery.motivations). None/empty → no motivation gate.
    motivation_any: Optional[list[str]] = None
    # AI-effect guard: the more personal prompts only fire once the trip has a
    # destination, so the AI never cold-opens an intimate question.
    requires_destination: bool = False
    # Per-dimension gates, keys like "structure_preference_max" /
    # "exploration_tolerance_min" → 0..1 thresholds.
    profile: dict[str, float] = Field(default_factory=dict)


class CuriosityPrompt(BaseModel):
    id: str
    source: CuriositySource
    trigger: CuriosityTrigger
    text: str
    rationale: str


# ── library loading ──────────────────────────────────────────────────────────

def load_library(path: Path | str = LIBRARY_PATH) -> list[CuriosityPrompt]:
    """Parse the YAML library into validated models. Raises on a malformed
    file — callers that must degrade gracefully catch and fall back to []."""
    raw = yaml.safe_load(Path(path).read_text(encoding="utf-8")) or []
    return [CuriosityPrompt.model_validate(entry) for entry in raw]


# ── delivery framing (the AI-effect counter) ─────────────────────────────────

def frame_curiosity_prompt(text: str) -> str:
    """Wrap a curiosity prompt with strict delivery instructions so it lands as
    a light optional aside rather than an AI interrogation."""
    return (
        "\n\n<curiosity_prompt>\n"
        f'You MAY end with this optional aside: "{text}"\n'
        "Delivery rules — important, because this comes from an AI and a "
        "heavy question can fall flat:\n"
        "- Give your genuinely useful answer FIRST; this is a throwaway line, "
        "not the point of the reply.\n"
        "- If you use it, drop it in as ONE short, casual line at the very end "
        "— like a friend musing aloud, never a survey or a deep interview.\n"
        "- It must be answerable in a few words or happily ignored. Do not "
        "wait for an answer and never repeat it on a later turn.\n"
        "- If it would feel intrusive, therapised, or off given what the "
        "traveler just said, drop it entirely and say nothing.\n"
        "</curiosity_prompt>\n"
    )


# ── helpers ──────────────────────────────────────────────────────────────────

def _enabled() -> bool:
    return os.getenv("CURIOSITY_INJECTOR_ENABLED", "true").strip().lower() not in (
        "false", "0", "no", "off",
    )


def is_today_iso(iso: Optional[str]) -> bool:
    return bool(iso) and str(iso)[:10] == date.today().isoformat()


def today_iso() -> str:
    return date.today().isoformat()


def _scores(user_doc: dict[str, Any]) -> dict[str, float]:
    pd = ((user_doc or {}).get("user_profile") or {}).get("profile_data") or {}
    return pd.get("personality_dimensions_scores") or {}


def _motivations(user_doc: dict[str, Any], trip: Optional[dict[str, Any]]) -> set[str]:
    pd = ((user_doc or {}).get("user_profile") or {}).get("profile_data") or {}
    out = {str(m).lower() for m in (pd.get("travel_motivations") or [])}
    out |= {str(m).lower() for m in (((trip or {}).get("discovery") or {}).get("motivations") or [])}
    return out


# ── injector ─────────────────────────────────────────────────────────────────

class CuriosityPromptInjector:
    """Selects zero or one curiosity prompt for a turn."""

    def __init__(
        self,
        library_path: Path | str = LIBRARY_PATH,
        library: Optional[list[CuriosityPrompt]] = None,
    ):
        if library is not None:
            self._library = library
            return
        try:
            self._library = load_library(library_path)
        except Exception:
            logger.warning("curiosity library failed to load; injector disabled.", exc_info=True)
            self._library = []

    def select(
        self,
        state: str,
        user_doc: dict[str, Any],
        session_state: dict[str, Any],
        force: bool = False,
        trip: Optional[dict[str, Any]] = None,
    ) -> Optional[CuriosityPrompt]:
        """Return one :class:`CuriosityPrompt` or ``None``. Deterministic for the
        same (user, state, day). ``force`` (e.g. the user explicitly asks for a
        prompt) bypasses the once-per-session and high-structure gates."""
        if not _enabled():
            return None
        if not force and (session_state or {}).get("curiosity_used_this_session"):
            return None
        scores = _scores(user_doc)
        if not force and float(scores.get("structure_preference", 0.5) or 0.5) > 0.7:
            return None

        motivations = _motivations(user_doc, trip)
        has_destination = bool((trip or {}).get("destinations"))
        candidates = [
            p for p in self._library
            if state in p.trigger.states
            and self._matches(p, scores, motivations, has_destination)
        ]
        if not candidates:
            return None
        idx = self._stable_index(user_doc, state, len(candidates))
        return candidates[idx]

    # ------------------------------------------------------------------

    @staticmethod
    def _matches(
        p: CuriosityPrompt,
        scores: dict[str, float],
        motivations: set[str],
        has_destination: bool,
    ) -> bool:
        if p.trigger.requires_destination and not has_destination:
            return False
        if p.trigger.motivation_any and not (set(m.lower() for m in p.trigger.motivation_any) & motivations):
            return False
        for key, threshold in (p.trigger.profile or {}).items():
            if key.endswith("_max"):
                if float(scores.get(key[:-4], 0.5) or 0.5) > threshold:
                    return False
            elif key.endswith("_min"):
                if float(scores.get(key[:-4], 0.5) or 0.5) < threshold:
                    return False
        return True

    @staticmethod
    def _stable_index(user_doc: dict[str, Any], state: str, n: int) -> int:
        seed = str(user_doc.get("id") or user_doc.get("user_id") or "anon")
        digest = hashlib.sha256(f"{seed}:{state}:{today_iso()}".encode()).hexdigest()
        return int(digest, 16) % n


# ── module singleton ─────────────────────────────────────────────────────────

_INJECTOR: Optional[CuriosityPromptInjector] = None


def get_injector() -> CuriosityPromptInjector:
    global _INJECTOR
    if _INJECTOR is None:
        _INJECTOR = CuriosityPromptInjector()
    return _INJECTOR
