"""
Tests for the Telegram webhook handler.

Tests cover:
- Security layers (secret token, secret path, IP whitelist, rate limiting)
- Payload validation
- /start command linking
- Regular message routing to orchestrator
"""

import json
import time
from unittest.mock import MagicMock, patch

import pytest

# Patch heavy dependencies before importing the webhook module
with patch("agentic_traveler.webhook.FirestoreUserTool"), \
     patch("agentic_traveler.webhook.OrchestratorAgent"):
    from agentic_traveler.webhook import (
        app, _is_rate_limited, _user_timestamps, _rate_lock,
    )


@pytest.fixture
def client():
    """Flask test client."""
    app.config["TESTING"] = True
    with app.test_client() as c:
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


def test_wrong_url_secret_rejected(client, valid_update):
    """Layer 2: Wrong secret in URL path → 403."""
    resp = client.post(
        "/webhook/wrong-secret",
        json=valid_update,
        headers={"X-Telegram-Bot-Api-Secret-Token": "wrong"},
    )
    assert resp.status_code == 403


@patch("agentic_traveler.webhook.SECRET_TOKEN", "test-secret")
def test_wrong_header_secret_rejected(client, valid_update):
    """Layer 1: Correct URL but wrong header → 403."""
    resp = client.post(
        "/webhook/test-secret",
        json=valid_update,
        headers={"X-Telegram-Bot-Api-Secret-Token": "wrong-header"},
    )
    assert resp.status_code == 403


@patch("agentic_traveler.webhook.SECRET_TOKEN", "test-secret")
@patch("agentic_traveler.webhook._is_telegram_ip", return_value=False)
@patch.dict("os.environ", {"SKIP_IP_CHECK": ""})
def test_non_telegram_ip_rejected(mock_ip, client, valid_update):
    """Layer 3: Non-Telegram IP → 403."""
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


@patch("agentic_traveler.webhook.SECRET_TOKEN", "test-secret")
@patch.dict("os.environ", {"SKIP_IP_CHECK": "1"})
def test_empty_payload_rejected(client):
    """Layer 5: No JSON body → 400."""
    resp = client.post(
        "/webhook/test-secret",
        data="not json",
        content_type="text/plain",
        headers={"X-Telegram-Bot-Api-Secret-Token": "test-secret"},
    )
    assert resp.status_code == 400


@patch("agentic_traveler.webhook.SECRET_TOKEN", "test-secret")
@patch.dict("os.environ", {"SKIP_IP_CHECK": "1"})
def test_non_message_update_accepted(client):
    """Non-message updates (edited, inline) are silently accepted."""
    resp = client.post(
        "/webhook/test-secret",
        json={"update_id": 1, "edited_message": {}},
        headers={"X-Telegram-Bot-Api-Secret-Token": "test-secret"},
    )
    assert resp.status_code == 200


# ── /start Command Tests ──


@patch("agentic_traveler.webhook.SECRET_TOKEN", "test-secret")
@patch.dict("os.environ", {"SKIP_IP_CHECK": "1"})
@patch("agentic_traveler.webhook.send_telegram_message")
@patch("agentic_traveler.webhook._user_tool")
def test_start_with_submission_id(mock_tool, mock_send, client, start_update):
    """/start <submissionId> links the user and sends welcome."""
    mock_tool.link_telegram_user.return_value = {"user_name": "Alice"}

    resp = client.post(
        "/webhook/test-secret",
        json=start_update,
        headers={"X-Telegram-Bot-Api-Secret-Token": "test-secret"},
    )
    assert resp.status_code == 200
    mock_tool.link_telegram_user.assert_called_once_with("abc123", "67890")
    mock_send.assert_called_once()
    assert "Alice" in mock_send.call_args[0][1]


@patch("agentic_traveler.webhook.SECRET_TOKEN", "test-secret")
@patch.dict("os.environ", {"SKIP_IP_CHECK": "1"})
@patch("agentic_traveler.webhook.send_telegram_message")
@patch("agentic_traveler.webhook._user_tool")
def test_start_unknown_submission(mock_tool, mock_send, client):
    """/start with unknown submissionId → error message."""
    mock_tool.link_telegram_user.return_value = None

    update = {
        "update_id": 1,
        "message": {
            "message_id": 1,
            "chat": {"id": 123},
            "from": {"id": 456},
            "text": "/start unknown_id",
            "date": 1700000000,
        },
    }
    resp = client.post(
        "/webhook/test-secret",
        json=update,
        headers={"X-Telegram-Bot-Api-Secret-Token": "test-secret"},
    )
    assert resp.status_code == 200
    assert "couldn't find" in mock_send.call_args[0][1].lower()


# ── Regular Message Tests ──


@patch("agentic_traveler.webhook.SECRET_TOKEN", "test-secret")
@patch.dict("os.environ", {"SKIP_IP_CHECK": "1"})
@patch("agentic_traveler.webhook.send_telegram_message")
@patch("agentic_traveler.webhook.edit_telegram_message")
@patch("agentic_traveler.webhook._orchestrator")
def test_regular_message(mock_orch, mock_edit, mock_send, client, valid_update):
    """Regular message → orchestrator → reply."""
    mock_orch.process_request.return_value = {"text": "Hello Alice!"}

    # mock_send returns a dummy message_id for the placeholder
    mock_send.return_value = 42

    resp = client.post(
        "/webhook/test-secret",
        json=valid_update,
        headers={"X-Telegram-Bot-Api-Secret-Token": "test-secret"},
    )
    assert resp.status_code == 200
    mock_orch.process_request.assert_called_once_with("67890", "Hello bot!")
    
    # Verify the two-step flow
    mock_send.assert_called_once_with(12345, "⏳ Thinking...")
    mock_edit.assert_called_once_with(12345, 42, "Hello Alice!")


# ── Health Check ──


def test_health_check(client):
    """GET /health returns 200."""
    resp = client.get("/health")
    assert resp.status_code == 200
    assert resp.get_json()["status"] == "ok"
