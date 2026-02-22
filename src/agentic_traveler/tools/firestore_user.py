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
        Perform a partial (merge) update on a user document.

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

        ref.set(fields, merge=True)
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
