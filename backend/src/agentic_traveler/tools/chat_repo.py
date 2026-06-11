"""
ChatRepository — Supabase-backed persistence for chat threads and messages.

This is the SOURCE OF TRUTH for the user-facing web chat view. It is separate
from `conversations` (which is the agent's rolling context window — kept small
and compacted, never shown to the user).

All methods use the service-role DB client and bypass RLS. Callers (the web
chat router, the Telegram router) are responsible for authorization.
"""

import logging
import time
from typing import Any, Callable, Dict, List, Literal, Optional, TypeVar

from agentic_traveler.tools.db_client import get_db

logger = logging.getLogger(__name__)

T = TypeVar("T")


def _retry(op: Callable[[], T], *, attempts: int = 3, base_delay: float = 0.25,
           label: str = "chat_repo") -> T:
    """
    Run `op` with bounded retries against transient DB failures (network
    hiccups, connection resets). The service role + Supabase REST layer
    surfaces these as generic exceptions; we cannot reliably distinguish
    transient from permanent without parsing supabase-py's error envelope,
    so we retry a fixed number of times with exponential backoff and let
    the caller log the final failure.
    """
    last_exc: Exception | None = None
    for i in range(attempts):
        try:
            return op()
        except Exception as exc:
            last_exc = exc
            if i + 1 == attempts:
                break
            delay = base_delay * (2 ** i)
            logger.warning(
                "%s op failed (attempt %d/%d): %s — retrying in %.2fs",
                label, i + 1, attempts, exc, delay,
            )
            time.sleep(delay)
    assert last_exc is not None
    raise last_exc

# Per-thread caches keyed by user_id. Threads are created exactly once per user
# and never change UUID, so caching them avoids one round-trip per message.
_thread_cache: Dict[str, str] = {}


class ChatRepository:
    """Append-only persistence for chat threads and messages."""

    # ------------------------------------------------------------------
    # Threads
    # ------------------------------------------------------------------

    def get_or_create_direct_ai_thread(self, user_id: str) -> str:
        """
        Return the user's direct_ai thread UUID, creating it on first use.

        Uses the partial unique index `chat_threads_owner_direct_ai_uniq`
        to make creation idempotent against concurrent inserts.
        """
        cached = _thread_cache.get(user_id)
        if cached:
            return cached

        db = get_db()

        # Fast path: read existing thread.
        existing = (
            db.table("chat_threads")
            .select("id")
            .eq("owner_user_id", user_id)
            .eq("kind", "direct_ai")
            .maybe_single()
            .execute()
        )
        if existing and existing.data:
            tid = existing.data["id"]
            _thread_cache[user_id] = tid
            return tid

        # Slow path: insert. Rely on the partial unique index to guard against races.
        try:
            inserted = (
                db.table("chat_threads")
                .insert({
                    "owner_user_id": user_id,
                    "kind": "direct_ai",
                })
                .execute()
            )
            tid = inserted.data[0]["id"]
            _thread_cache[user_id] = tid
            return tid
        except Exception:
            # Likely a unique-violation race — re-read.
            logger.warning(
                "chat_threads insert failed for user %s; re-reading after race.",
                user_id,
            )
            existing = (
                db.table("chat_threads")
                .select("id")
                .eq("owner_user_id", user_id)
                .eq("kind", "direct_ai")
                .single()
                .execute()
            )
            tid = existing.data["id"]
            _thread_cache[user_id] = tid
            return tid

    # ------------------------------------------------------------------
    # Messages — writes
    # ------------------------------------------------------------------

    def append_user_message(
        self,
        user_id: str,
        body: str,
        source: Literal["web", "telegram"],
        thread_id: Optional[str] = None,
    ) -> Dict[str, Any]:
        """Insert a row with sender_type='user'. Returns {id, thread_id, created_at}."""
        tid = thread_id or self.get_or_create_direct_ai_thread(user_id)
        row = _retry(lambda: (
            get_db()
            .table("messages")
            .insert({
                "thread_id": tid,
                "sender_type": "user",
                "sender_user_id": user_id,
                "body": body,
                "source": source,
            })
            .execute()
        ), label="append_user_message")
        return _shape(row.data[0])

    def append_agent_message(
        self,
        user_id: str,
        body: str,
        source: Literal["web", "telegram"],
        thread_id: Optional[str] = None,
        metadata: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        """Insert a row with sender_type='agent'. Returns {id, thread_id, created_at}."""
        tid = thread_id or self.get_or_create_direct_ai_thread(user_id)
        row = _retry(lambda: (
            get_db()
            .table("messages")
            .insert({
                "thread_id": tid,
                "sender_type": "agent",
                "sender_user_id": None,
                "body": body,
                "source": source,
                "metadata": metadata or {},
            })
            .execute()
        ), label="append_agent_message")
        return _shape(row.data[0])

    def append_pair(
        self,
        user_id: str,
        user_body: str,
        agent_body: str,
        source: Literal["web", "telegram"],
        agent_metadata: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Dict[str, Any]]:
        """
        Convenience: write both the user message and the agent reply against
        the same thread. Looks the thread up exactly once.
        """
        tid = self.get_or_create_direct_ai_thread(user_id)
        user_row = self.append_user_message(user_id, user_body, source, thread_id=tid)
        agent_row = self.append_agent_message(
            user_id, agent_body, source, thread_id=tid, metadata=agent_metadata,
        )
        return {"user": user_row, "agent": agent_row}

    # ------------------------------------------------------------------
    # Messages — reads
    # ------------------------------------------------------------------

    def list_messages(
        self,
        user_id: str,
        before_id: Optional[int] = None,
        after_id: Optional[int] = None,
        limit: int = 50,
    ) -> List[Dict[str, Any]]:
        """
        Return messages in id DESC order, up to `limit`.
        Cursor: id < before_id (exclusive) OR id > after_id (exclusive).
        Pass None to get the newest page.
        """
        limit = max(1, min(limit, 100))
        tid = self.get_or_create_direct_ai_thread(user_id)
        q = (
            get_db()
            .table("messages")
            .select("id, thread_id, sender_type, sender_user_id, body, source, metadata, created_at")
            .eq("thread_id", tid)
        )
        if after_id is not None:
            q = q.gt("id", after_id).order("id", desc=False).limit(limit)
            resp = q.execute()
            rows = resp.data or []
            rows.reverse()  # Match standard DESC order
            return [_shape(r) for r in rows]
            
        q = q.order("id", desc=True).limit(limit)
        if before_id is not None:
            q = q.lt("id", before_id)
        resp = q.execute()
        return [_shape(r) for r in (resp.data or [])]

    def search_messages(
        self,
        user_id: str,
        query: str,
        limit: int = 25,
    ) -> List[Dict[str, Any]]:
        """
        Full-text search inside the user's thread. Uses plainto_tsquery('simple', q)
        so user input doesn't need to be FTS-safe. Returns up to `limit` hits in
        id DESC order (newest match first).
        """
        query = (query or "").strip()
        if not query:
            return []

        limit = max(1, min(limit, 100))
        tid = self.get_or_create_direct_ai_thread(user_id)

        # supabase-py supports the `text_search` filter with config + type.
        resp = (
            get_db()
            .table("messages")
            .select("id, thread_id, sender_type, sender_user_id, body, source, metadata, created_at")
            .eq("thread_id", tid)
            .order("id", desc=True)
            .limit(limit)
            .text_search("body_tsv", query, options={"config": "simple", "type": "plain"})
            .execute()
        )
        return [_shape(r) for r in (resp.data or [])]


# ----------------------------------------------------------------------
# helpers
# ----------------------------------------------------------------------

def _shape(row: Dict[str, Any]) -> Dict[str, Any]:
    """Normalize a DB row into the API shape. Currently a passthrough."""
    return {
        "id": row["id"],
        "thread_id": row["thread_id"],
        "sender_type": row["sender_type"],
        "sender_user_id": row.get("sender_user_id"),
        "body": row["body"],
        "source": row.get("source"),
        "metadata": row.get("metadata") or {},
        "created_at": row["created_at"],
    }
