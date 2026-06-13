"""Task 54 — deterministic Traveler-DNA write path.

Two ways an answer reaches the profile:
  - a tapped profile chip → :func:`profile_selection_to_side_effect` (validate) →
    :func:`apply_profile_patch` (merge ``answered_questions[qid]``). Zero LLM.
  - a free-text reaction ("not big on museums") → :func:`reaction_to_profile_patch`
    (one ``flash-lite`` extraction via the shipped ``ProfileAgent`` path).

Plus :func:`backfill_user`, which marks the questions a legacy Tally submission
already answered so no migrated user is ever re-asked them.
"""

from __future__ import annotations

import logging
from typing import Any, Optional

from agentic_traveler.orchestrator.profile_questions import (
    BY_ID,
    PROFILE_QUESTIONS,
    legal_option_values,
)
from agentic_traveler.orchestrator.sagas.base import SideEffect

logger = logging.getLogger(__name__)

SKIP_SENTINEL = "__skip__"


def profile_selection_to_side_effect(
    qid: str, values: list[str]
) -> Optional[SideEffect]:
    """Validate a tapped profile answer against the bank; return a
    ``profile_patch`` SideEffect or ``None`` if illegal (unknown question or no
    legal value). Pure, no LLM — the profile sibling of
    ``slot_selection_to_side_effect``. The client registry is never trusted
    (trust-but-verify, Task 54 AC-4)."""
    q = BY_ID.get(qid)
    if q is None:
        return None
    clean = [str(v) for v in (values or []) if str(v)]
    if not clean:
        return None
    if clean == [SKIP_SENTINEL]:
        return SideEffect(
            kind="profile_patch",
            payload={"qid": qid, "value": SKIP_SENTINEL, "source": "chat_tap"},
        )
    legal = legal_option_values(qid)
    chosen = [v for v in clean if v in legal]
    if not chosen:
        return None
    if not q.allow_multi:
        chosen = chosen[:1]
    value: Any = chosen if q.allow_multi else chosen[0]
    return SideEffect(
        kind="profile_patch",
        payload={"qid": qid, "value": value, "source": "chat_tap"},
    )


def apply_profile_patch(user_id: str, payload: dict, repo: Any = None) -> None:
    """Apply a ``profile_patch`` deterministically (zero LLM): merge
    ``answered_questions[qid] = {value, set_at, source}`` into the profile."""
    qid = payload.get("qid")
    if not user_id or not qid:
        return
    if repo is None:
        from agentic_traveler.tools.user_repo import UserRepository

        repo = UserRepository()
    repo.merge_answered_question(
        user_id, qid, payload.get("value"), payload.get("source", "chat_tap")
    )


def reaction_to_profile_patch(
    user_id: str,
    user_doc: dict,
    text: str,
    token_records: Optional[list] = None,
    agent: Any = None,
) -> None:
    """One ``flash-lite`` extraction of a volunteered preference folded into the
    DNA via the shipped ``ProfileAgent.save_preference`` path. cost: flash_lite."""
    if agent is None:
        from agentic_traveler.orchestrator.profile_agent import ProfileAgent

        agent = ProfileAgent()
    agent.save_preference(text, user_doc, user_id, token_records=token_records)


def backfill_user(user_id: str, form_response: dict, repo: Any) -> int:
    """Mark every bank question whose ``tally_key`` is present in ``form_response``
    as answered (``source='tally_backfill'``). Idempotent and non-destructive:
    :meth:`UserRepository.merge_answered_question` never clobbers a chat/dna answer
    with a backfill. Returns the count marked (Task 54 AC-9)."""
    marked = 0
    for q in PROFILE_QUESTIONS:
        if q.binding != "profile" or not q.tally_key:
            continue
        raw = form_response.get(q.tally_key)
        if raw in (None, "", []):
            continue
        repo.merge_answered_question(user_id, q.id, raw, "tally_backfill")
        marked += 1
    return marked
