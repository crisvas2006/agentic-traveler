import os
os.environ["FRONTEND_ORIGIN"] = "http://localhost:3000"

from datetime import datetime, timezone, timedelta
from unittest.mock import MagicMock, patch
import pytest
from fastapi.testclient import TestClient

# Patch UserRepository and OrchestratorAgent before importing FastAPI app
with patch("agentic_traveler.interfaces.routers.telegram.UserRepository"), \
     patch("agentic_traveler.interfaces.routers.telegram.OrchestratorAgent"):
    from agentic_traveler.interfaces.main import app
    import agentic_traveler.interfaces.routers.telegram as telegram_router
    telegram_router.FRONTEND_ORIGIN = "http://localhost:3000"

@pytest.fixture
def client():
    """FastAPI test client."""
    with TestClient(app) as c:
        yield c

@pytest.fixture
def unlinked_update():
    """Message from unlinked Telegram user."""
    return {
        "update_id": 10,
        "message": {
            "message_id": 10,
            "chat": {"id": 11111},
            "from": {"id": 22222, "first_name": "UnlinkedUser"},
            "text": "Hello bot!",
            "date": 1700000000,
        },
    }

@pytest.fixture
def start_unlinked_update():
    """Message from unlinked Telegram user doing plain /start."""
    return {
        "update_id": 11,
        "message": {
            "message_id": 11,
            "chat": {"id": 11111},
            "from": {"id": 22222, "first_name": "UnlinkedUser"},
            "text": "/start",
            "date": 1700000000,
        },
    }

# Test 1: Unregistered / unlinked users are blocked on regular messages
@patch.dict("os.environ", {"TELEGRAM_SECRET_TOKEN": "test-secret", "SKIP_IP_CHECK": "1", "FRONTEND_ORIGIN": "http://localhost:3000"})
@patch("agentic_traveler.interfaces.routers.telegram.send_telegram_message")
@patch("agentic_traveler.interfaces.routers.telegram.get_user_tool")
def test_unlinked_user_is_blocked(mock_tool, mock_send, client, unlinked_update):
    # Simulate that user is not found in database
    mock_tool.return_value.get_user_by_telegram_id.return_value = None

    resp = client.post(
        "/webhook/test-secret",
        json=unlinked_update,
        headers={"X-Telegram-Bot-Api-Secret-Token": "test-secret"},
    )
    assert resp.status_code == 200

    # Ensure message was sent directing them to register
    mock_send.assert_called_once()
    sent_text = mock_send.call_args[0][1]
    assert "create an account" in sent_text
    assert "http://localhost:3000" in sent_text

# Test 2: Unregistered / unlinked users are blocked on plain `/start`
@patch.dict("os.environ", {"TELEGRAM_SECRET_TOKEN": "test-secret", "SKIP_IP_CHECK": "1", "FRONTEND_ORIGIN": "http://localhost:3000"})
@patch("agentic_traveler.interfaces.routers.telegram.send_telegram_message")
@patch("agentic_traveler.interfaces.routers.telegram.get_user_tool")
def test_unlinked_user_start_is_blocked(mock_tool, mock_send, client, start_unlinked_update):
    # Simulate that user is not found in database
    mock_tool.return_value.get_user_by_telegram_id.return_value = None

    resp = client.post(
        "/webhook/test-secret",
        json=start_unlinked_update,
        headers={"X-Telegram-Bot-Api-Secret-Token": "test-secret"},
    )
    assert resp.status_code == 200

    mock_send.assert_called_once()
    sent_text = mock_send.call_args[0][1]
    assert "create an account" in sent_text
    assert "http://localhost:3000" in sent_text

# Test 3: `/start link_<uuid>` bypasses the unlinked guard and executes the linking flow
@patch.dict("os.environ", {
    "TELEGRAM_SECRET_TOKEN": "test-secret",
    "SKIP_IP_CHECK": "1",
})
@patch("agentic_traveler.interfaces.routers.telegram.send_telegram_message")
@patch("agentic_traveler.interfaces.routers.telegram.get_user_tool")
@patch("agentic_traveler.tools.db_client.get_db")
def test_start_link_bypasses_guard_and_links(mock_get_db, mock_tool, mock_send, client):
    """A valid UUID token is looked up in the DB, accounts are linked, token consumed."""
    token = "550e8400-e29b-41d4-a716-446655440000"
    future = (datetime.now(timezone.utc) + timedelta(minutes=9)).isoformat()

    # Mock the DB chain: .table().select().eq().maybe_single().execute()
    mock_db = MagicMock()
    mock_get_db.return_value = mock_db
    mock_db.table.return_value.select.return_value.eq.return_value.maybe_single.return_value.execute.return_value.data = {
        "user_id": "web-user-uuid-12345",
        "expires_at": future,
        "form_response": {"travel_bubble": "Solo"}
    }
    # .delete().eq().execute() — just needs to not raise
    mock_db.table.return_value.delete.return_value.eq.return_value.execute.return_value = None

    mock_tool.return_value.link_telegram_to_web_user.return_value = (True, "✅ Linked!")
    mock_tool.return_value.get_user_by_telegram_id.return_value = None  # unlinked before call

    update = {
        "update_id": 12,
        "message": {
            "message_id": 12,
            "chat": {"id": 11111},
            "from": {"id": 22222, "first_name": "UnlinkedUser"},
            "text": f"/start link_{token}",
            "date": 1700000000,
        },
    }

    resp = client.post(
        "/webhook/test-secret",
        json=update,
        headers={"X-Telegram-Bot-Api-Secret-Token": "test-secret"},
    )
    assert resp.status_code == 200

    # Verify the linking method was called with the right web user id
    mock_tool.return_value.link_telegram_to_web_user.assert_called_once_with(
        "web-user-uuid-12345", "22222"
    )

    # Verify the confirmation message was sent back
    mock_send.assert_called_once_with(11111, "✅ Linked!")


# Test 4: Expired token is rejected gracefully
@patch.dict("os.environ", {
    "TELEGRAM_SECRET_TOKEN": "test-secret",
    "SKIP_IP_CHECK": "1",
})
@patch("agentic_traveler.interfaces.routers.telegram.send_telegram_message")
@patch("agentic_traveler.interfaces.routers.telegram.get_user_tool")
@patch("agentic_traveler.tools.db_client.get_db")
def test_start_link_expired_token(mock_get_db, mock_tool, mock_send, client):
    """An expired token sends a friendly error and is cleaned up."""
    token = "550e8400-e29b-41d4-a716-446655440001"
    past = (datetime.now(timezone.utc) - timedelta(minutes=1)).isoformat()

    mock_db = MagicMock()
    mock_get_db.return_value = mock_db
    mock_db.table.return_value.select.return_value.eq.return_value.maybe_single.return_value.execute.return_value.data = {
        "user_id": "web-user-uuid-12345",
        "expires_at": past,
    }
    mock_db.table.return_value.delete.return_value.eq.return_value.execute.return_value = None

    update = {
        "update_id": 13,
        "message": {
            "message_id": 13,
            "chat": {"id": 11111},
            "from": {"id": 22222, "first_name": "UnlinkedUser"},
            "text": f"/start link_{token}",
            "date": 1700000000,
        },
    }

    resp = client.post(
        "/webhook/test-secret",
        json=update,
        headers={"X-Telegram-Bot-Api-Secret-Token": "test-secret"},
    )
    assert resp.status_code == 200

    mock_tool.return_value.link_telegram_to_web_user.assert_not_called()
    mock_send.assert_called_once()
    assert "expired" in mock_send.call_args[0][1].lower()


# Test 5: Non-existent / already-consumed token is rejected
@patch.dict("os.environ", {
    "TELEGRAM_SECRET_TOKEN": "test-secret",
    "SKIP_IP_CHECK": "1",
})
@patch("agentic_traveler.interfaces.routers.telegram.send_telegram_message")
@patch("agentic_traveler.interfaces.routers.telegram.get_user_tool")
@patch("agentic_traveler.tools.db_client.get_db")
def test_start_link_unknown_token(mock_get_db, mock_tool, mock_send, client):
    """A token not found in DB sends an invalid-link error."""
    token = "00000000-0000-0000-0000-000000000000"

    mock_db = MagicMock()
    mock_get_db.return_value = mock_db
    mock_db.table.return_value.select.return_value.eq.return_value.maybe_single.return_value.execute.return_value.data = None

    update = {
        "update_id": 14,
        "message": {
            "message_id": 14,
            "chat": {"id": 11111},
            "from": {"id": 22222, "first_name": "UnlinkedUser"},
            "text": f"/start link_{token}",
            "date": 1700000000,
        },
    }

    resp = client.post(
        "/webhook/test-secret",
        json=update,
        headers={"X-Telegram-Bot-Api-Secret-Token": "test-secret"},
    )
    assert resp.status_code == 200

    mock_tool.return_value.link_telegram_to_web_user.assert_not_called()
    mock_send.assert_called_once()
    assert "invalid" in mock_send.call_args[0][1].lower()


# Test 6: Non-UUID token (e.g. "123") is rejected gracefully without PostgREST/PostgreSQL syntax crashes
@patch.dict("os.environ", {
    "TELEGRAM_SECRET_TOKEN": "test-secret",
    "SKIP_IP_CHECK": "1",
})
@patch("agentic_traveler.interfaces.routers.telegram.send_telegram_message")
@patch("agentic_traveler.interfaces.routers.telegram.get_user_tool")
@patch("agentic_traveler.tools.db_client.get_db")
def test_start_link_non_uuid_token(mock_get_db, mock_tool, mock_send, client):
    """A non-UUID token deep-link parameter is caught by validation and returns an invalid-link error."""
    token = "123"

    mock_db = MagicMock()
    mock_get_db.return_value = mock_db

    update = {
        "update_id": 15,
        "message": {
            "message_id": 15,
            "chat": {"id": 11111},
            "from": {"id": 22222, "first_name": "UnlinkedUser"},
            "text": f"/start link_{token}",
            "date": 1700000000,
        },
    }

    resp = client.post(
        "/webhook/test-secret",
        json=update,
        headers={"X-Telegram-Bot-Api-Secret-Token": "test-secret"},
    )
    assert resp.status_code == 200

    # Ensure no database table queries were even executed for link_tokens lookup
    mock_db.table.assert_not_called()
    mock_tool.return_value.link_telegram_to_web_user.assert_not_called()
    
    mock_send.assert_called_once()
    assert "invalid" in mock_send.call_args[0][1].lower()
