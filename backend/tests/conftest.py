import os
from unittest.mock import MagicMock

# Mock the supabase client for unit tests so they don't need real credentials.
# Integration tests set _INTEGRATION_TESTS=1 and the real client is used.
if not os.getenv("_INTEGRATION_TESTS"):
    # Stub supabase at the module level so unit tests never need real env vars.
    import sys
    supabase_mock = MagicMock()
    sys.modules.setdefault("supabase", supabase_mock)

    # Also keep google.cloud.firestore mocked in case any utility script
    # (tally_webhook, delete_firestore_records) gets imported transitively.
    firestore_mock = MagicMock()
    sys.modules.setdefault("google.cloud.firestore", firestore_mock)
    sys.modules.setdefault("google.cloud.firestore_v1", MagicMock())
    sys.modules.setdefault("google.cloud.firestore_v1.base_query", MagicMock())
