"""
Shared fixtures for integration tests.

These fixtures talk to the REAL Firestore database and use real
Gemini API keys.  Test data is written with a ``_test: true`` marker
field and cleaned up after each test (or session).
"""

import logging
import os
import uuid
import pytest
from dotenv import load_dotenv
from google.cloud import firestore  # type: ignore
from agentic_traveler.tools.firestore_user import FirestoreUserTool
from agentic_traveler.orchestrator.agent import OrchestratorAgent

load_dotenv()

# Signal to the root conftest.py that integration tests are running,
# so it does NOT mock google.cloud.firestore.
os.environ["_INTEGRATION_TESTS"] = "1"

logger = logging.getLogger(__name__)

PROJECT_ID = os.getenv("GOOGLE_PROJECT_ID")
DATABASE_ID = "agentic-traveler-db"

# ---------------------------------------------------------------------------
# Firestore (session-scoped — one connection for the whole run)
# ---------------------------------------------------------------------------

@pytest.fixture(scope="session")
def firestore_user_tool():
    """Single FirestoreUserTool instance used by BOTH fixture writes and the orchestrator."""
    return FirestoreUserTool(project_id=PROJECT_ID, database_id=DATABASE_ID)


@pytest.fixture
def orchestrator(firestore_user_tool):
    """OrchestratorAgent wired to the shared FirestoreUserTool."""
    return OrchestratorAgent(firestore_user_tool=firestore_user_tool)


# ---------------------------------------------------------------------------
# Test user lifecycle (function-scoped — fresh user per test)
# ---------------------------------------------------------------------------

@pytest.fixture
def test_user(firestore_user_tool):
    """
    Create a recognisable test user in Firestore, yield it,
    then delete it regardless of test outcome.

    Uses the SAME Firestore client as the OrchestratorAgent
    (via firestore_user_tool.db) to avoid any connection mismatches.
    """
    short_id = uuid.uuid4().hex[:8]
    doc_id = f"test_integration_{short_id}"
    telegram_id = f"test_tg_{short_id}"

    user_data = {
        "user_name": "IntegrationBot",
        "telegramUserId": telegram_id,
        "preferences": {
            "vibes": "adventure",
            "avoidances": "crowds",
            "pace": "Relaxed",
        },
        "_test": True,  # marker so stale data is easy to find
    }

    # --- Arrange: write test user using the SAME client the tool reads from ---
    doc_ref = firestore_user_tool.db.collection("users").document(doc_id)
    doc_ref.set(user_data)

    # Hard-verify the user is queryable before any test runs
    found = firestore_user_tool.get_user_by_telegram_id(telegram_id)
    assert found is not None, (
        f"FIXTURE BUG: wrote user {doc_id} with telegramUserId={telegram_id} "
        f"but get_user_by_telegram_id returned None. "
        f"DB project={firestore_user_tool.db.project}"
    )

    yield {**user_data, "_doc_id": doc_id, "_telegram_id": telegram_id}

    # --- Cleanup: always delete ---
    doc_ref.delete()


# ---------------------------------------------------------------------------
# Session-level safety sweep (backstop for any leaked test data)
# ---------------------------------------------------------------------------

@pytest.fixture(scope="session", autouse=True)
def sweep_test_data(firestore_user_tool):
    """After ALL integration tests, delete any documents with _test == True."""
    yield  # let all tests run first
    query = firestore_user_tool.db.collection("users").where("_test", "==", True)
    for doc in query.stream():
        doc.reference.delete()
