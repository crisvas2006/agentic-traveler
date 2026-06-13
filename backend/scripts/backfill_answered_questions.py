"""Task 54 — one-time backfill of ``profile_data.answered_questions`` from the
legacy Tally ``form_response``, so migrated users are never re-asked what Tally
already covered. Idempotent and non-destructive (a backfill never clobbers a
chat/dna answer).

Run (from the repo root, with the backend venv active):

    .\\backend\\.venv\\Scripts\\python backend\\scripts\\backfill_answered_questions.py

Reads + writes the live Supabase project configured in ``backend/.env`` — review
before running against production.
"""

from __future__ import annotations

import logging

from agentic_traveler.orchestrator.profile_write import backfill_user
from agentic_traveler.tools.db_client import get_db
from agentic_traveler.tools.user_repo import UserRepository

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("backfill_answered_questions")


def main() -> None:
    repo = UserRepository()
    res = get_db().table("user_profiles").select("user_id, form_response").execute()
    rows = res.data or []

    users_updated = 0
    for row in rows:
        user_id = row.get("user_id")
        form_response = row.get("form_response") or {}
        if not user_id or not form_response:
            continue
        marked = backfill_user(user_id, form_response, repo)
        if marked:
            users_updated += 1
            logger.info("Backfilled %d answer(s) for user %s", marked, user_id)

    logger.info("Backfill complete. Users updated: %d / %d scanned.", users_updated, len(rows))


if __name__ == "__main__":
    main()
