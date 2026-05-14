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
with patch("agentic_traveler.interfaces.webhook.UserRepository"), \
     patch("agentic_traveler.interfaces.webhook.OrchestratorAgent"):
    from agentic_traveler.interfaces.webhook import (
        app, _is_rate_limited, _user_timestamps, _rate_lock,
    )


@pytest.fixture
def client():
    """Flask test client."""
    app.config["TESTING"] = True
    with app.test_client() as c:
        yield c


@pytest.fixture(autouse=True)
def run_threads_synchronously():
    """Patch threading.Thread to execute the target immediately for testing."""
    with patch("threading.Thread") as mock_thread:
        def side_effect(target, args=(), kwargs={}, **_):
            target(*args, **kwargs)
            return MagicMock()
        mock_thread.side_effect = side_effect
        yield mock_thread


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


@patch("agentic_traveler.interfaces.webhook.SECRET_TOKEN", "test-secret")
def test_wrong_header_secret_rejected(client, valid_update):
    """Layer 1: Correct URL but wrong header → 403."""
    resp = client.post(
        "/webhook/test-secret",
        json=valid_update,
        headers={"X-Telegram-Bot-Api-Secret-Token": "wrong-header"},
    )
    assert resp.status_code == 403


@patch("agentic_traveler.interfaces.webhook.SECRET_TOKEN", "test-secret")
@patch("agentic_traveler.interfaces.webhook._is_telegram_ip", return_value=False)
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


@patch("agentic_traveler.interfaces.webhook.SECRET_TOKEN", "test-secret")
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


@patch("agentic_traveler.interfaces.webhook.SECRET_TOKEN", "test-secret")
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


@patch("agentic_traveler.interfaces.webhook.SECRET_TOKEN", "test-secret")
@patch.dict("os.environ", {"SKIP_IP_CHECK": "1"})
@patch("agentic_traveler.interfaces.webhook.edit_telegram_message")
@patch("agentic_traveler.interfaces.webhook.send_telegram_message")
@patch("agentic_traveler.interfaces.webhook.get_user_tool")
@patch("agentic_traveler.tools.db_client.get_db")
@patch("agentic_traveler.orchestrator.profile_agent.ProfileAgent")
def test_start_with_submission_id(mock_profile_agent, mock_get_db, mock_tool, mock_send, mock_edit, client, start_update):
    """/start <submissionId> links the user and sends welcome."""
    # ProfileAgent.build_initial_profile returns a greeting + structured data
    mock_profile_agent.return_value.build_initial_profile.return_value = {
        "greeting": "Hi Alice! Welcome aboard.",
        "summary": "Adventure traveler",
    }
    mock_tool.return_value.link_telegram_user.return_value = ({"name": "Alice", "id": "uuid-1", "user_profile": {}}, True)

    resp = client.post(
        "/webhook/test-secret",
        json=start_update,
        headers={"X-Telegram-Bot-Api-Secret-Token": "test-secret"},
    )
    assert resp.status_code == 200
    mock_tool.return_value.link_telegram_user.assert_called_once_with("abc123", "67890")

    # Check that we sent a placeholder and a greeting
    assert mock_send.call_count >= 1
    # Alice should appear in either the edit (welcome back) or in the greeting message
    found_alice = any("Alice" in str(c) for c in mock_edit.call_args_list)
    found_alice = found_alice or any("Alice" in str(c) for c in mock_send.call_args_list)
    assert found_alice is True


@patch("agentic_traveler.interfaces.webhook.SECRET_TOKEN", "test-secret")
@patch.dict("os.environ", {"SKIP_IP_CHECK": "1"})
@patch("agentic_traveler.interfaces.webhook.send_telegram_message")
@patch("agentic_traveler.interfaces.webhook.get_user_tool")
def test_start_unknown_submission(mock_tool, mock_send, client):
    """/start with unknown submissionId → error message."""
    mock_tool.return_value.link_telegram_user.return_value = (None, False)

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
    assert "completed the travel form" in mock_send.call_args[0][1].lower()


# ── Regular Message Tests ──


@patch("agentic_traveler.interfaces.webhook.SECRET_TOKEN", "test-secret")
@patch.dict("os.environ", {"SKIP_IP_CHECK": "1"})
@patch("agentic_traveler.interfaces.webhook.send_telegram_message")
@patch("agentic_traveler.interfaces.webhook.edit_telegram_message")
@patch("agentic_traveler.interfaces.webhook.get_orchestrator")
def test_regular_message(mock_orch, mock_edit, mock_send, client, valid_update):
    """Regular message → orchestrator → reply."""
    mock_orch.return_value.process_request.return_value = {"text": "Hello Alice!"}

    # mock_send returns a dummy message_id for the placeholder
    mock_send.return_value = 42

    resp = client.post(
        "/webhook/test-secret",
        json=valid_update,
        headers={"X-Telegram-Bot-Api-Secret-Token": "test-secret"},
    )
    assert resp.status_code == 200
    from unittest.mock import ANY
    mock_orch.return_value.process_request.assert_called_once_with("67890", "Hello bot!", status_callback=ANY)
    
    # Verify the two-step flow
    mock_send.assert_called_once_with(12345, "⏳ Thinking...")
    mock_edit.assert_called_once_with(12345, 42, "Hello Alice!")


# ── Health Check ──


def test_health_check(client):
    """GET /health returns 200."""
    resp = client.get("/health")
    assert resp.status_code == 200
    assert resp.get_json()["status"] == "ok"


# ── Tally Webhook Tests ──


@patch("agentic_traveler.interfaces.webhook.TALLY_WEBHOOK_TOKEN", "test-tally-token")
def test_tally_webhook_unauthorized(client):
    """Tally webhook without correct auth header → 401."""
    resp = client.post(
        "/tally-webhook",
        json={"data": {"responseId": "123"}},
        headers={"Authorization": "Bearer wrong-token"},
    )
    assert resp.status_code == 401


@patch("agentic_traveler.interfaces.webhook.TALLY_WEBHOOK_TOKEN", "test-tally-token")
@patch("agentic_traveler.tools.db_client.get_db")
def test_tally_webhook_success(mock_get_db, client):
    """Valid Tally submission upserts to users and user_profiles."""
    # Mock Supabase responses
    mock_db = mock_get_db.return_value
    mock_table = mock_db.table.return_value
    mock_upsert = mock_table.upsert.return_value
    mock_execute = mock_upsert.execute
    
    # Return a fake ID for the user insert
    mock_execute.return_value.data = [{"id": "new-user-uuid"}]

    tally_payload = {
        "data": {
            "responseId": "sub_123",
            "fields": [
                {"key": "question_Ldg8Ep", "type": "SHORT_ANSWER", "value": "Alice"},
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
    assert resp.get_json()["status"] == "ok"

    # Both upserts use the same mock table return_value, so check call_args_list
    upsert_calls = mock_table.upsert.call_args_list
    assert len(upsert_calls) == 2
    
    users_upsert_args = upsert_calls[0][0][0]
    assert users_upsert_args["submission_id"] == "sub_123"
    assert users_upsert_args["name"] == "Alice"
    assert users_upsert_args["location"] == "Paris"
    assert users_upsert_args["source"] == "tally"

    profiles_upsert_args = upsert_calls[1][0][0]
    assert profiles_upsert_args["user_id"] == "new-user-uuid"
    assert profiles_upsert_args["form_response"]["travel_bubble"] == "Solo"

