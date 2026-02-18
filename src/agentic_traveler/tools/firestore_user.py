from typing import Optional, Dict, Any
from google.cloud import firestore # type: ignore

class FirestoreUserTool:
    """Tool for interacting with the Firestore 'users' collection."""

    def __init__(self, project_id: str = "agentic-traveler-db"):
        self.db = firestore.Client(project=project_id)
        self.users_collection = self.db.collection("users")

    def get_user_by_telegram_id(self, telegram_id: str) -> Optional[Dict[str, Any]]:
        """
        Fetches a user document by their Telegram User ID.
        
        Args:
            telegram_id: The Telegram User ID to search for.
            
        Returns:
            The user document as a dictionary, or None if not found.
        """
        # Note: This assumes there is a field 'telegramUserId' in the user document.
        # If the mapping is stored differently (e.g. document ID is the telegram ID),
        # this logic needs to change.
        # Based on specs, we might need to query for it.
        
        # Query for the user with this telegramUserId
        query = self.users_collection.where("telegramUserId", "==", telegram_id).limit(1)
        results = list(query.stream())
        
        if not results:
            return None
            
        return results[0].to_dict()

    def get_user_by_id(self, user_id: str) -> Optional[Dict[str, Any]]:
        """
        Fetches a user document by their Firestore Document ID.
        """
        doc = self.users_collection.document(user_id).get()
        if doc.exists:
            return doc.to_dict()
        return None
