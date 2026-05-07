from typing import Optional, Dict, Any
import os
import logging
from google.cloud import firestore  # type: ignore
from google.cloud.firestore_v1.base_query import FieldFilter  # type: ignore
from dotenv import load_dotenv

load_dotenv()

logger = logging.getLogger(__name__)


class FirestoreUserTool:
    """Tool for interacting with the Firestore 'users' collection."""

    def __init__(
        self,
        project_id: Optional[str] = None,
        database_id: str = "agentic-traveler-db",
    ):
        project = project_id or os.getenv("GOOGLE_PROJECT_ID")
        self.db = firestore.Client(project=project, database=database_id)
        self.users_collection = self.db.collection("users")

    def get_user_by_telegram_id(self, telegram_id: str) -> Optional[Dict[str, Any]]:
        """
        Fetches a user document by their Telegram User ID.

        Returns:
            The user document as a dictionary, or None if not found.
        """
        doc, _ref = self.get_user_with_ref(telegram_id)
        return doc

    def get_user_ref_by_telegram_id(self, telegram_id: str):
        """
        Returns the Firestore DocumentReference for a user, or None.

        Useful when you need to perform partial updates on the document.
        """
        _doc, ref = self.get_user_with_ref(telegram_id)
        return ref

    def get_user_with_ref(self, telegram_id: str):
        """
        Fetch both the user document dict AND its DocumentReference in
        a **single** Firestore query.

        Returns:
            Tuple of (user_dict, DocumentReference), or (None, None).
        """
        query = self.users_collection.where(
            filter=FieldFilter("telegramUserId", "==", telegram_id)
        ).limit(1)
        results = list(query.stream())

        if not results:
            return None, None

        return results[0].to_dict(), results[0].reference

    def update_user_fields(self, telegram_id: str, fields: Dict[str, Any]) -> bool:
        """
        Perform a partial update on a user document.

        Supports dot-notation keys (e.g. "user_profile.summary") to write
        into nested maps without overwriting sibling fields.

        Args:
            telegram_id: Telegram user ID to look up.
            fields: Dict of top-level or dot-notation fields to upsert.

        Returns:
            True if the update succeeded, False if user not found.
        """
        ref = self.get_user_ref_by_telegram_id(telegram_id)
        if not ref:
            logger.warning("Cannot update — user %s not found.", telegram_id)
            return False

        # ref.update() (unlike ref.set(..., merge=True)) correctly interprets
        # dot-notation keys as nested Firestore paths and does a partial merge.
        ref.update(fields)
        logger.info("Updated user %s with fields: %s", telegram_id, list(fields.keys()))
        return True

    def get_user_by_id(self, user_id: str) -> Optional[Dict[str, Any]]:
        """
        Fetches a user document by their Firestore Document ID.
        """
        doc = self.users_collection.document(user_id).get()
        if doc.exists:
            return doc.to_dict()
        return None

    def link_telegram_user(
        self, submission_id: str, telegram_id: str
    ) -> tuple[Optional[Dict[str, Any]], bool]:
        """
        Find a user by their Tally submissionId and set their telegramUserId.
        If the telegram_id already exists in another document, merge the new
        submission data into the old document and delete the new submission document.

        Returns:
            Tuple of (user_dict, is_update) where:
            - user_dict is the user document dict if found and linked, or None.
            - is_update is True if an existing profile was updated, False if it was a new profile.
        """
        query = self.users_collection.where(
            filter=FieldFilter("submissionId", "==", submission_id)
        ).limit(1)
        results = list(query.stream())

        if not results:
            logger.warning("No user found with submissionId=%s", submission_id)
            return None, False

        new_doc_snap = results[0]
        new_doc_dict = new_doc_snap.to_dict()
        new_doc_ref = new_doc_snap.reference

        # Check if this telegram user already exists
        existing_doc, existing_ref = self.get_user_with_ref(telegram_id)

        if existing_doc and existing_ref:
            # Make sure we aren't merging the exact same document
            if existing_ref.id == new_doc_ref.id:
                new_doc_ref.set({"telegramUserId": telegram_id}, merge=True)
                new_doc_dict["telegramUserId"] = telegram_id
                return new_doc_dict, False

            # Merge new submission into old document
            merge_data = new_doc_dict.copy()
            merge_data["telegramUserId"] = telegram_id

            existing_ref.set(merge_data, merge=True)
            logger.info("Merged submissionId=%s into existing user %s", submission_id, telegram_id)

            # Delete the new orphan submission
            new_doc_ref.delete()

            updated_doc = existing_doc.copy()
            updated_doc.update(merge_data)
            return updated_doc, True

        else:
            # New linking
            new_doc_ref.set({"telegramUserId": telegram_id}, merge=True)
            logger.info("Linked telegramUserId=%s to submissionId=%s", telegram_id, submission_id)
            new_doc_dict["telegramUserId"] = telegram_id
            return new_doc_dict, False
