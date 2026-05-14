"""
UserRepository — Supabase-backed persistence layer for user data.

All methods return plain dicts. There is no DocumentReference concept;
the UUID primary key (``user_doc["id"]``) is used for all FK relations.

The assembled ``user_doc`` dict uses a nested shape so that downstream
consumers (credit_manager, off_topic_guard, etc.) can read sub-keys like
``user_doc["credits"]["balance"]`` without needing to know the DB schema.
"""

import logging
from typing import Any, Dict, Optional, Tuple

from agentic_traveler.tools.db_client import get_db

logger = logging.getLogger(__name__)


class UserRepository:
    """CRUD access layer for the ``users`` table and its satellite tables."""

    # ------------------------------------------------------------------
    # Fetch
    # ------------------------------------------------------------------

    def get_user_by_telegram_id(self, telegram_id: str) -> Optional[Dict[str, Any]]:
        """
        Fetch a user dict by Telegram ID, with all sub-tables joined.

        Returns:
            Assembled user dict (mirrors old Firestore shape), or None.
        """
        doc, _uid = self.get_user_with_ref(telegram_id)
        return doc

    def get_user_ref_by_telegram_id(self, telegram_id: str) -> Optional[str]:
        """
        Return the user UUID for the given Telegram ID, or None.

        The UUID is the Supabase equivalent of the Firestore DocumentReference.
        """
        _doc, uid = self.get_user_with_ref(telegram_id)
        return uid

    def get_user_with_ref(
        self, telegram_id: str
    ) -> Tuple[Optional[Dict[str, Any]], Optional[str]]:
        """
        Fetch the user dict AND their UUID in a single call.

        Returns:
            (user_dict, user_id) or (None, None) if not found.
        """
        try:
            resp = (
                get_db()
                .table("users")
                .select(
                    "*, user_profiles(*), credits(*), conversations(*), off_topic_state(*)"
                )
                .eq("telegram_id", telegram_id)
                .maybe_single()
                .execute()
            )
        except Exception:
            logger.exception("Failed to fetch user by telegram_id=%s", telegram_id)
            return None, None

        if not resp.data:
            return None, None

        user_id = resp.data["id"]
        assembled = _assemble_user_doc(resp.data)
        return assembled, user_id

    def get_user_by_id(self, user_id: str) -> Optional[Dict[str, Any]]:
        """Fetch a user dict by their UUID."""
        try:
            resp = (
                get_db()
                .table("users")
                .select(
                    "*, user_profiles(*), credits(*), conversations(*), off_topic_state(*)"
                )
                .eq("id", user_id)
                .maybe_single()
                .execute()
            )
        except Exception:
            logger.exception("Failed to fetch user by id=%s", user_id)
            return None

        if not resp.data:
            return None
        return _assemble_user_doc(resp.data)

    # ------------------------------------------------------------------
    # Update
    # ------------------------------------------------------------------

    def update_user_fields(self, telegram_id: str, fields: Dict[str, Any]) -> bool:
        """
        Update top-level user columns by Telegram ID.

        Unlike Firestore's dot-notation, ``fields`` must map to real columns
        in the ``users`` table.  Sub-table updates go through dedicated
        repository methods (update_profile, etc.).

        Returns:
            True if at least one row was updated, False otherwise.
        """
        try:
            resp = (
                get_db()
                .table("users")
                .update(fields)
                .eq("telegram_id", telegram_id)
                .execute()
            )
            updated = bool(resp.data)
            if not updated:
                logger.warning("update_user_fields: no row for telegram_id=%s", telegram_id)
            return updated
        except Exception:
            logger.exception("Failed to update user fields for telegram_id=%s", telegram_id)
            return False

    def upsert_profile(self, user_id: str, profile_data: Dict[str, Any], summary: str = "") -> None:
        """Upsert the user_profiles row for the given user UUID."""
        try:
            get_db().table("user_profiles").upsert(
                {
                    "user_id": user_id,
                    "profile_data": profile_data,
                    "summary": summary,
                }
            ).execute()
        except Exception:
            logger.exception("Failed to upsert profile for user_id=%s", user_id)

    def upsert_form_response(self, user_id: str, form_response: Dict[str, Any]) -> None:
        """Upsert the raw Tally form response into user_profiles."""
        try:
            get_db().table("user_profiles").upsert(
                {"user_id": user_id, "form_response": form_response}
            ).execute()
        except Exception:
            logger.exception("Failed to upsert form_response for user_id=%s", user_id)

    def upsert_structured_profile(self, user_id: str, profile_data: Dict[str, Any]) -> None:
        """
        Upsert the AI-generated structured profile_data into user_profiles.

        This is distinct from upsert_form_response (raw Tally data) and
        upsert_profile (full profile with summary). Use this specifically
        after ProfileAgent generates a new structured profile schema.
        """
        try:
            get_db().table("user_profiles").upsert(
                {"user_id": user_id, "profile_data": profile_data}
            ).execute()
        except Exception:
            logger.exception("Failed to upsert structured profile for user_id=%s", user_id)

    # ------------------------------------------------------------------
    # Link (replaces link_telegram_user)
    # ------------------------------------------------------------------

    def link_telegram_user(
        self, submission_id: str, telegram_id: str
    ) -> Tuple[Optional[Dict[str, Any]], bool]:
        """
        Find a user by their Tally submissionId and set their telegram_id.

        If another user row already carries this telegram_id, the new
        submission data is merged into the existing row and the orphan row
        is deleted (same semantics as the old Firestore implementation).

        Returns:
            (user_dict, is_update) where is_update=True means an existing
            Telegram-linked profile was updated rather than freshly linked.
        """
        db = get_db()

        # 1. Find by submission_id
        try:
            new_resp = (
                db.table("users")
                .select("*")
                .eq("submission_id", submission_id)
                .maybe_single()
                .execute()
            )
        except Exception:
            logger.exception("link_telegram_user: query by submission_id failed")
            return None, False

        if not new_resp.data:
            logger.warning("No user with submission_id=%s", submission_id)
            return None, False

        new_row = new_resp.data
        new_user_id = new_row["id"]

        # 2. Check if telegram_id already belongs to another user
        try:
            existing_resp = (
                db.table("users")
                .select("id, telegram_id")
                .eq("telegram_id", telegram_id)
                .maybe_single()
                .execute()
            )
        except Exception:
            logger.exception("link_telegram_user: query by telegram_id failed")
            return None, False

        existing_row = existing_resp.data if existing_resp else None

        if existing_row and existing_row["id"] != new_user_id:
            # Merge: copy submission_id onto the existing row, delete orphan
            try:
                db.table("users").update(
                    {"submission_id": submission_id}
                ).eq("id", existing_row["id"]).execute()

                db.table("users").delete().eq("id", new_user_id).execute()

                logger.info(
                    "Merged submission_id=%s into existing user telegram_id=%s",
                    submission_id, telegram_id,
                )
                merged, uid = self.get_user_with_ref(telegram_id)
                return merged, True
            except Exception:
                logger.exception("link_telegram_user: merge failed")
                return None, False

        # 3. Simple fresh link
        try:
            db.table("users").update(
                {"telegram_id": telegram_id}
            ).eq("id", new_user_id).execute()

            logger.info(
                "Linked telegram_id=%s to submission_id=%s", telegram_id, submission_id
            )
            linked, _ = self.get_user_with_ref(telegram_id)
            return linked, False
        except Exception:
            logger.exception("link_telegram_user: update failed")
            return None, False


# ------------------------------------------------------------------
# Private helpers
# ------------------------------------------------------------------


def _assemble_user_doc(row: Dict[str, Any]) -> Dict[str, Any]:
    """
    Assemble a flat Supabase joined row into the nested dict shape that
    the existing downstream code expects.

    Old shape (Firestore):
        user_doc["credits"]["balance"]
        user_doc["conversation_history"]["recent_messages"]
        user_doc["off_topic"]["count"]
        user_doc["user_profile"]["profile_data"]

    This function preserves that shape so credit_manager, off_topic_guard,
    and conversation_manager do not need to change.
    """
    profile_row = row.get("user_profiles") or {}
    credits_row = row.get("credits") or {}
    conv_row = row.get("conversations") or {}
    ot_row = row.get("off_topic_state") or {}

    return {
        # Core identity
        "id": row.get("id"),
        "telegramUserId": row.get("telegram_id"),
        "submissionId": row.get("submission_id"),
        "name": row.get("name"),
        "user_name": row.get("name"),
        "location": row.get("location"),
        "source": row.get("source"),
        "created_at": row.get("created_at"),
        # Profile (nested under user_profile to match old shape)
        "user_profile": {
            "profile_data": profile_row.get("profile_data", {}),
            "form_response": profile_row.get("form_response", {}),
            "summary": profile_row.get("summary", ""),
            # Flatten profile_data fields so agents can read them directly
            **(profile_row.get("profile_data") or {}),
        },
        # Credits (nested under credits to match old shape)
        "credits": {
            "balance": credits_row.get("balance", 0),
            "initial_grant": credits_row.get("initial_grant", 0),
            "total_spent": credits_row.get("total_spent", 0),
            "used_promos": credits_row.get("used_promos", []),
        },
        # Conversation history (nested under conversation_history)
        "conversation_history": {
            "recent_messages": conv_row.get("recent_messages", []),
            "summary": conv_row.get("summary", ""),
        },
        # Off-topic state (nested under off_topic to match old shape)
        "off_topic": {
            "count": ot_row.get("count", 0),
            "last_flagged_ts": (
                ot_row.get("last_flagged_ts").isoformat()
                if ot_row.get("last_flagged_ts")
                else None
            ),
            "restricted_until": (
                ot_row.get("restricted_until").isoformat()
                if ot_row.get("restricted_until")
                else None
            ),
        },
    }
