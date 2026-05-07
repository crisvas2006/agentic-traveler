"""
Feedback logging tool — persists user feedback signals to Firestore.

Called by the orchestrator agent when it detects any feedback signal
(positive, negative, confusion, retry request, feature suggestion, etc.).
All writes are fire-and-forget (background thread) so they never block
the response to the user.

Firestore schema
----------------
Collection: feedback
Document  : <auto-id>
Fields:
    user_id              : str
    text                 : str      ← the feedback text as expressed by the user
    category             : str      ← see CATEGORIES below
    timestamp            : datetime (server timestamp)
    conversation_context : list     ← last ≤6 messages (3 exchanges) for context
        [{role: "user"|"agent", text: str, ts: str}, ...]
"""

import logging
import os
import threading
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)

# Allowed feedback categories.
CATEGORIES = {"positive", "negative", "confusion", "retry", "suggestion", "other"}

# How many recent messages to attach as context (3 exchanges = up to 6 entries).
CONTEXT_MESSAGES = 6


class FeedbackTool:
    def __init__(self):
        try:
            from google.cloud import firestore  # type: ignore

            project = os.getenv("GOOGLE_PROJECT_ID")
            self.db = firestore.Client(project=project, database="agentic-traveler-db")
        except Exception:
            logger.exception("Failed to initialize Firestore Client in FeedbackTool.")
            self.db = None

    def record(
        self,
        *,
        user_id: str,
        text: str,
        category: str,
        user_doc: Optional[Dict[str, Any]] = None,
        _sync: bool = False,
    ) -> None:
        """
        Persist a feedback entry asynchronously.

        Args:
            user_id:   Telegram user ID (string).
            text:      The feedback as expressed by the user.
            category:  One of: positive, negative, confusion, retry,
                       suggestion, other.
            user_doc:  Current user document (used to extract conversation
                       context). Pass None if not available.
            _sync:     If True, write synchronously (useful for tests).
        """
        safe_category = category if category in CATEGORIES else "other"
        
        logger.debug(
            "FeedbackTool.record called: user=%s, category=%s, text_len=%d",
            user_id, safe_category, len(text)
        )
        
        conversation_context = self._extract_context(user_doc)

        payload = {
            "user_id": user_id,
            "text": text,
            "category": safe_category,
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "conversation_context": conversation_context,
        }

        if _sync:
            self._write(payload)
        else:
            threading.Thread(
                target=self._write, args=(payload,), daemon=True
            ).start()

    # ── private helpers ──────────────────────────────────────────────────────

    @staticmethod
    def _extract_context(user_doc: Optional[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """Return at most the last CONTEXT_MESSAGES entries from conversation history."""
        if not user_doc:
            return []
        history = user_doc.get("conversation_history", {})
        recent = history.get("recent_messages", [])
        return recent[-CONTEXT_MESSAGES:]

    def _write(self, payload: Dict[str, Any]) -> None:
        """Write the payload to Firestore feedback collection."""
        if not self.db:
            logger.error("Skipping feedback write: Firestore client not initialized.")
            return

        try:
            self.db.collection("feedback").add(payload)
            logger.info(
                "💬 Feedback recorded | user=%s category=%s",
                payload["user_id"],
                payload["category"],
            )
        except Exception:
            logger.exception("Failed to record feedback to Firestore.")
