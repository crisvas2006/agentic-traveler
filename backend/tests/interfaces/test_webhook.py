import json
from unittest.mock import MagicMock, patch

import pytest
from fastapi.testclient import TestClient

# Patch heavy dependencies before importing the main module
with patch("agentic_traveler.interfaces.routers.telegram.UserRepository"), \
     patch("agentic_traveler.interfaces.routers.telegram.OrchestratorAgent"):
    from agentic_traveler.interfaces.main import app
    from agentic_traveler.interfaces.routers.telegram import (
        _is_rate_limited, _user_timestamps, _rate_lock,
    )


@pytest.fixture
def client():
    """FastAPI test client."""
    with TestClient(app) as c:
        yield c


@pytest.fixture(autouse=True)
def clear_rate_limits():
    """Reset rate limit state between tests."""
    with _rate_lock:
        _user_timestamps.clear()
    yield


@pytest.fixture
def valid_update():
    """Minimal valid Telegram message update."""
    return {
        "update_id": 1,
        "message": {
            "message_id": 1,
            "chat": {"id": 12345},
            "from": {"id": 67890, "first_name": "Alice"},
            "text": "Hello bot!",
            "date": 1700000000,
        },
    }


@pytest.fixture
def start_update():
    """Telegram /start update with submissionId."""
    return {
        "update_id": 2,
        "message": {
            "message_id": 2,
            "chat": {"id": 12345},
            "from": {"id": 67890, "first_name": "Alice"},
            "text": "/start abc123",
            "date": 1700000000,
        },
    }


# ── Security Tests ──


@patch.dict("os.environ", {"TELEGRAM_SECRET_TOKEN": "test-secret"})
def test_wrong_url_secret_rejected(client, valid_update):
    """Layer 2: Wrong secret in URL path → 403."""
    resp = client.post(
        "/webhook/wrong-secret",
        json=valid_update,
        headers={"X-Telegram-Bot-Api-Secret-Token": "wrong"},
    )
    assert resp.status_code == 403


@patch.dict("os.environ", {"TELEGRAM_SECRET_TOKEN": "test-secret"})
def test_wrong_header_secret_rejected(client, valid_update):
    """Layer 1: Correct URL but wrong header → 403."""
    resp = client.post(
        "/webhook/test-secret",
        json=valid_update,
        headers={"X-Telegram-Bot-Api-Secret-Token": "wrong-header"},
    )
    assert resp.status_code == 403


@patch.dict("os.environ", {"TELEGRAM_SECRET_TOKEN": "test-secret"})
@patch.dict("os.environ", {"SKIP_IP_CHECK": ""})
def test_non_telegram_ip_rejected(client, valid_update):
    """Layer 3: Non-Telegram IP → 403."""
    # TestClient doesn't send X-Forwarded-For by default, and its IP isn't in Telegram ranges
    resp = client.post(
        "/webhook/test-secret",
        json=valid_update,
        headers={"X-Telegram-Bot-Api-Secret-Token": "test-secret"},
    )
    assert resp.status_code == 403


# ── Rate Limiting Tests ──


def test_rate_limit_per_minute():
    """Layer 4: User is blocked after exceeding per-minute limit."""
    user_id = "rate-test-user"
    for _ in range(10):
        assert not _is_rate_limited(user_id)
    # 11th message should be rate-limited
    assert _is_rate_limited(user_id)


# ── Payload Validation Tests ──


@patch.dict("os.environ", {"TELEGRAM_SECRET_TOKEN": "test-secret", "SKIP_IP_CHECK": "1"})
def test_empty_payload_rejected(client):
    """Layer 5: No JSON body → 422 (FastAPI validation error)."""
    resp = client.post(
        "/webhook/test-secret",
        content=b"not json",
        headers={
            "X-Telegram-Bot-Api-Secret-Token": "test-secret",
            "Content-Type": "application/json"
        },
    )
    assert resp.status_code == 422


@patch.dict("os.environ", {"TELEGRAM_SECRET_TOKEN": "test-secret", "SKIP_IP_CHECK": "1"})
def test_non_message_update_accepted(client):
    """Non-message updates (edited, inline) are silently accepted."""
    resp = client.post(
        "/webhook/test-secret",
        json={"update_id": 1, "edited_message": {}},
        headers={"X-Telegram-Bot-Api-Secret-Token": "test-secret"},
    )
    assert resp.status_code == 200


# ── /start Command Tests ──


@patch.dict("os.environ", {"TELEGRAM_SECRET_TOKEN": "test-secret", "SKIP_IP_CHECK": "1"})
@patch("agentic_traveler.interfaces.routers.telegram.send_telegram_message")
def test_start_with_unsupported_submission_id(mock_send, client, start_update):
    """/start <submissionId> (legacy/unsupported deep-link parameter) warns user and returns 200."""
    resp = client.post(
        "/webhook/test-secret",
        json=start_update,
        headers={"X-Telegram-Bot-Api-Secret-Token": "test-secret"},
    )
    assert resp.status_code == 200
    mock_send.assert_called_once()
    assert "Invalid link parameter" in mock_send.call_args[0][1]


# ── Regular Message Tests ──


@patch.dict("os.environ", {"TELEGRAM_SECRET_TOKEN": "test-secret", "SKIP_IP_CHECK": "1"})
@patch("agentic_traveler.interfaces.routers.telegram.send_telegram_message")
@patch("agentic_traveler.interfaces.routers.telegram.edit_telegram_message")
@patch("agentic_traveler.interfaces.routers.telegram.get_orchestrator")
def test_regular_message(mock_orch, mock_edit, mock_send, client, valid_update):
    """Regular message → orchestrator → reply."""
    mock_orch.return_value.process_request.return_value = {"text": "Hello Alice!"}
    mock_send.return_value = 42

    resp = client.post(
        "/webhook/test-secret",
        json=valid_update,
        headers={"X-Telegram-Bot-Api-Secret-Token": "test-secret"},
    )
    assert resp.status_code == 200
    
    from unittest.mock import ANY
    mock_orch.return_value.process_request.assert_called_once_with("67890", "Hello bot!", status_callback=ANY)
    
    mock_send.assert_called_once_with(12345, "⏳ Thinking...")
    mock_edit.assert_called_once_with(12345, 42, "Hello Alice!")


# ── Health Check ──


def test_health_check(client):
    """GET /health returns 200."""
    resp = client.get("/health")
    assert resp.status_code == 200
    assert resp.json()["status"] == "ok"


# ── Tally Webhook Tests ──


@patch.dict("os.environ", {"TALLY_WEBHOOK_TOKEN": "test-tally-token"})
def test_tally_webhook_unauthorized(client):
    """Tally webhook without correct auth header → 401."""
    resp = client.post(
        "/tally-webhook",
        json={"data": {"responseId": "123"}},
        headers={"Authorization": "Bearer wrong-token"},
    )
    assert resp.status_code == 401


@patch.dict("os.environ", {"TALLY_WEBHOOK_TOKEN": "test-tally-token"})
@patch("agentic_traveler.interfaces.routers.tally.get_db")
def test_tally_webhook_dropped_missing_token(mock_get_db, client):
    """Submissions without idToken are ignored/dropped with 200 status."""
    tally_payload = {
        "data": {
            "responseId": "sub_123",
            "fields": [
                {"key": "question_1rxjbl", "type": "SHORT_ANSWER", "value": "Paris"},
                {"key": "question_aByWrb", "type": "SHORT_ANSWER", "value": "Solo"}
            ]
        }
    }

    resp = client.post(
        "/tally-webhook",
        json=tally_payload,
        headers={"Authorization": "Bearer test-tally-token"},
    )
    
    assert resp.status_code == 200
    assert resp.json()["status"] == "dropped"
    assert resp.json()["reason"] == "Missing idToken"
