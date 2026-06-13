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

        if resp is None or not resp.data:
            return None, None

        user_id = resp.data["id"]
        assembled = _assemble_user_doc(resp.data)
        return assembled, user_id

    def get_user_by_id(self, user_id: str) -> Optional[Dict[str, Any]]:
        """Fetch a user dict by their UUID. Merge user related data from all user-connected tables into one dict."""
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

        if resp is None or not resp.data:
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

        Pops the 'summary' from profile_data and stores it in the dedicated
        'summary' column, matching the layout used by the ProfileAgent.
        """
        try:
            data_copy = dict(profile_data)
            summary = data_copy.pop("summary", "")
            get_db().table("user_profiles").upsert(
                {
                    "user_id": user_id,
                    "profile_data": data_copy,
                    "summary": summary,
                }
            ).execute()
        except Exception:
            logger.exception("Failed to upsert structured profile for user_id=%s", user_id)

    def merge_answered_question(
        self, user_id: str, qid: str, value: Any, source: str = "chat_tap"
    ) -> None:
        """Deterministically record a Traveler-DNA answer (Task 54): merge
        ``profile_data.answered_questions[qid] = {value, set_at, source}`` into the
        existing profile_data. Zero LLM, idempotent. A ``tally_backfill`` never
        clobbers a richer chat/dna answer (Task 54 AC-9). The partial upsert
        preserves the ``summary`` column (PostgREST updates only given columns)."""
        from datetime import datetime, timezone

        try:
            res = (
                get_db()
                .table("user_profiles")
                .select("profile_data")
                .eq("user_id", user_id)
                .maybe_single()
                .execute()
            )
            profile_data = dict((res.data or {}).get("profile_data") or {}) if res else {}
            answered = dict(profile_data.get("answered_questions") or {})
            existing = answered.get(qid)
            if (
                source == "tally_backfill"
                and isinstance(existing, dict)
                and existing.get("source") in ("chat_tap", "chat_text", "dna_page")
            ):
                return
            answered[qid] = {
                "value": value,
                "set_at": datetime.now(timezone.utc).isoformat(),
                "source": source,
            }
            profile_data["answered_questions"] = answered
            get_db().table("user_profiles").upsert(
                {"user_id": user_id, "profile_data": profile_data}
            ).execute()
        except Exception:
            logger.exception(
                "Failed to merge answered question qid=%s user_id=%s", qid, user_id
            )

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
            # Merge: copy submission_id and profile onto the existing row, delete orphan.
            # Behavior: New details (name, location, form_response) override old ones.
            try:
                # 1. Fetch the new profile data before deleting the row
                new_profile_resp = (
                    db.table("user_profiles")
                    .select("form_response")
                    .eq("user_id", new_user_id)
                    .maybe_single()
                    .execute()
                )
                new_form_response = (
                    new_profile_resp.data.get("form_response")
                    if new_profile_resp and new_profile_resp.data
                    else {}
                )

                # 2. Delete the new orphan row first to free up submission_id constraint
                db.table("users").delete().eq("id", new_user_id).execute()

                # 3. Update existing row with new metadata
                db.table("users").update(
                    {
                        "submission_id": submission_id,
                        "name": new_row.get("name"),
                        "location": new_row.get("location"),
                    }
                ).eq("id", existing_row["id"]).execute()

                # 4. Update the profile with new form response
                self.upsert_form_response(existing_row["id"], new_form_response)

                logger.info(
                    "Merged submission_id=%s into existing user telegram_id=%s (overrode profile)",
                    submission_id,
                    telegram_id,
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

    def link_telegram_to_web_user(self, user_id: str, telegram_id: str) -> Tuple[bool, str]:
        """
        Link a Telegram account (telegram_id) to an authenticated web user (user_id).

        Returns:
            (success, message)
        """
        db = get_db()

        # 1. Check if this telegram_id is already linked to a different user
        try:
            existing = (
                db.table("users")
                .select("id, telegram_id")
                .eq("telegram_id", telegram_id)
                .maybe_single()
                .execute()
            )
        except Exception:
            logger.exception("link_telegram_to_web_user: check existing failed")
            return False, "Database error during collision check."

        if existing and existing.data:
            if existing.data["id"] != user_id:
                return False, "This Telegram account is already linked to a different profile."
            else:
                return True, "Your Telegram chat is already connected to your web account."

        # 2. Perform the update
        try:
            resp = (
                db.table("users")
                .update({"telegram_id": telegram_id})
                .eq("id", user_id)
                .execute()
            )
            if resp and resp.data:
                logger.info("Successfully linked telegram_id=%s to web user_id=%s", telegram_id, user_id)
                return True, "✅ Linked! Your Telegram chat is now connected to your web account."
            else:
                return False, "User profile not found."
        except Exception:
            logger.exception("link_telegram_to_web_user: update failed")
            return False, "Database error during link update."


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
            # Supabase returns timestamps as ISO strings — use them directly.
            "last_flagged_ts": ot_row.get("last_flagged_ts"),
            "restricted_until": ot_row.get("restricted_until"),
        },
    }
