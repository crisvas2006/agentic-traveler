"""
Shared fixtures for integration tests.

These fixtures talk to the REAL Supabase database and use real
Gemini API keys.  Test data is written with a ``_test_run`` prefix
on telegram_id and cleaned up after each test (or session).
"""

import logging
import uuid
import pytest
from dotenv import load_dotenv

from agentic_traveler.tools.user_repo import UserRepository
from agentic_traveler.tools.db_client import get_db
from agentic_traveler.orchestrator.agent import OrchestratorAgent

load_dotenv()

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# UserRepository (session-scoped — one instance for the whole run)
# ---------------------------------------------------------------------------


@pytest.fixture(scope="session")
def user_repo():
    """Single UserRepository instance used by BOTH fixture writes and the orchestrator."""
    return UserRepository()


@pytest.fixture
def orchestrator(user_repo):
    """OrchestratorAgent wired to the shared UserRepository."""
    return OrchestratorAgent(user_repo=user_repo)


# ---------------------------------------------------------------------------
# Test user lifecycle (function-scoped — fresh user per test)
# ---------------------------------------------------------------------------


@pytest.fixture
def test_user(user_repo):
    """
    Create a recognisable test user in Supabase, yield it,
    then delete it regardless of test outcome.
    """
    short_id = uuid.uuid4().hex[:8]
    submission_id = f"test_sub_{short_id}"
    telegram_id = f"test_tg_{short_id}"

    user_data = {
        "name": "IntegrationBot",
        "submission_id": submission_id,
        "source": "tally",
        "location": "TestCity",
    }

    # Write test user row
    db = get_db()
    resp = db.table("users").insert(user_data).execute()
    assert resp.data, f"FIXTURE BUG: failed to insert test user {user_data}"
    user_id = resp.data[0]["id"]

    # Link telegram_id
    db.table("users").update({"telegram_id": telegram_id}).eq("id", user_id).execute()

    # Seed minimal credits so the credit gate passes
    db.table("credits").insert({
        "user_id": user_id,
        "balance": 500,
        "initial_grant": 500,
        "total_spent": 0,
        "used_promos": [],
    }).execute()

    # Hard-verify the user is queryable before any test runs
    found = user_repo.get_user_by_telegram_id(telegram_id)
    assert found is not None, (
        f"FIXTURE BUG: wrote user with telegram_id={telegram_id} "
        f"but get_user_by_telegram_id returned None."
    )

    yield {**user_data, "_user_id": user_id, "_telegram_id": telegram_id}

    # Cleanup: cascades via FK ON DELETE CASCADE to all satellite tables
    db.table("users").delete().eq("id", user_id).execute()


# ---------------------------------------------------------------------------
# Session-level safety sweep (backstop for any leaked test data)
# ---------------------------------------------------------------------------


@pytest.fixture(scope="session", autouse=True)
def sweep_test_data():
    """After ALL integration tests, delete any rows whose telegram_id starts with 'test_tg_'."""
    yield  # let all tests run first
    try:
        db = get_db()
        db.table("users").delete().like("telegram_id", "test_tg_%").execute()
        logger.info("Integration test sweep complete.")
    except Exception:
        logger.exception("Failed to sweep integration test data.")
