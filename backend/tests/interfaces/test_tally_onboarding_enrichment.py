from datetime import datetime, timezone, timedelta
from unittest.mock import MagicMock, patch, ANY

import pytest
from fastapi.testclient import TestClient

# Mock heavy dependencies before imports
with patch("agentic_traveler.interfaces.routers.telegram.UserRepository"), \
     patch("agentic_traveler.interfaces.routers.telegram.OrchestratorAgent"):
    from agentic_traveler.interfaces.main import app

@pytest.fixture
def client():
    """FastAPI test client."""
    with TestClient(app) as c:
        yield c


# ── 1. Telegram Linking & Invitation Tests ──

@patch.dict("os.environ", {
    "TELEGRAM_SECRET_TOKEN": "test-secret",
    "SKIP_IP_CHECK": "1",
})
@patch("agentic_traveler.interfaces.routers.telegram.send_telegram_message")
@patch("agentic_traveler.interfaces.routers.telegram.get_user_tool")
@patch("agentic_traveler.tools.db_client.get_db")
def test_telegram_link_with_complete_profile(mock_get_db, mock_tool, mock_send, client):
    """If profile is complete, do not generate tally token or send invitation."""
    token = "550e8400-e29b-41d4-a716-446655440000"
    future = (datetime.now(timezone.utc) + timedelta(minutes=9)).isoformat()

    mock_db = MagicMock()
    mock_get_db.return_value = mock_db
    
    # Mock token lookup in link_tokens
    mock_db.table.return_value.select.return_value.eq.return_value.maybe_single.return_value.execute.return_value.data = {
        "user_id": "web-user-uuid-123",
        "expires_at": future,
    }
    
    # Mock user profile check - complete form_response
    mock_db.table.return_value.select.return_value.eq.return_value.maybe_single.return_value.execute.side_effect = [
        # First call is token select
        MagicMock(data={"user_id": "web-user-uuid-123", "expires_at": future}),
        # Second call is user_profiles select
        MagicMock(data={"form_response": {"travel_bubble": "Solo"}})
    ]

    mock_tool.return_value.link_telegram_to_web_user.return_value = (True, "✅ Linked!")
    mock_tool.return_value.get_user_by_telegram_id.return_value = None

    update = {
        "update_id": 1,
        "message": {
            "message_id": 1,
            "chat": {"id": 11111},
            "from": {"id": 22222},
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
    
    # Linked success sent, but NO invitation recommendation message sent
    assert mock_send.call_count == 1
    mock_send.assert_any_call(11111, "✅ Linked!")


@patch.dict("os.environ", {
    "TELEGRAM_SECRET_TOKEN": "test-secret",
    "SKIP_IP_CHECK": "1",
})
@patch("agentic_traveler.interfaces.routers.telegram.send_telegram_message")
@patch("agentic_traveler.interfaces.routers.telegram.get_user_tool")
@patch("agentic_traveler.tools.db_client.get_db")
def test_telegram_link_with_incomplete_profile(mock_get_db, mock_tool, mock_send, client):
    """If profile is incomplete, generate tally token and send thoughtful invitation."""
    token = "550e8400-e29b-41d4-a716-446655440000"
    future = (datetime.now(timezone.utc) + timedelta(minutes=9)).isoformat()

    mock_db = MagicMock()
    mock_get_db.return_value = mock_db
    
    # 1. Mock token lookup (link_tokens select)
    # 2. Mock profile lookup (user_profiles select) -> None
    # 3. Mock active tally submission token check (link_tokens select) -> None
    # 4. Mock insert of new tally submission token
    mock_db.table.return_value.select.return_value.eq.return_value.maybe_single.return_value.execute.side_effect = [
        MagicMock(data={"user_id": "web-user-uuid-123", "expires_at": future}), # token query
        MagicMock(data=None), # profile query (incomplete)
    ]
    
    # Mock token check returned empty (no active token)
    mock_db.table.return_value.select.return_value.eq.return_value.eq.return_value.execute.return_value.data = []
    
    # Mock insert tally submission token
    mock_db.table.return_value.insert.return_value.execute.return_value.data = [{"token": "tally-uuid-token"}]

    mock_tool.return_value.link_telegram_to_web_user.return_value = (True, "✅ Linked!")
    mock_tool.return_value.get_user_by_telegram_id.return_value = None

    update = {
        "update_id": 2,
        "message": {
            "message_id": 2,
            "chat": {"id": 11111},
            "from": {"id": 22222},
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
    
    # Both linking confirmation AND recommendation sent
    assert mock_send.call_count == 2
    mock_send.assert_any_call(11111, "✅ Linked!")
    
    invitation_text = mock_send.call_args_list[1][0][1]
    assert "A Thoughtful Recommendation for Your Travels" in invitation_text
    assert "tally.so/r/ODPGak?idToken=tally-uuid-token" in invitation_text
    assert "valid for 7 days" in invitation_text


# ── 2. Telegram Plain /start Welcome Test ──

@patch.dict("os.environ", {
    "TELEGRAM_SECRET_TOKEN": "test-secret",
    "SKIP_IP_CHECK": "1",
})
@patch("agentic_traveler.interfaces.routers.telegram.send_telegram_message")
@patch("agentic_traveler.interfaces.routers.telegram.get_user_tool")
def test_telegram_plain_start_for_linked_user(mock_tool, mock_send, client):
    """Plain /start greets an already linked user nicely instead of blocking them."""
    mock_tool.return_value.get_user_by_telegram_id.return_value = {"name": "Bob", "id": "web-user-123"}

    update = {
        "update_id": 3,
        "message": {
            "message_id": 3,
            "chat": {"id": 11111},
            "from": {"id": 22222},
            "text": "/start",
            "date": 1700000000,
        },
    }

    resp = client.post(
        "/webhook/test-secret",
        json=update,
        headers={"X-Telegram-Bot-Api-Secret-Token": "test-secret"},
    )
    assert resp.status_code == 200
    
    mock_send.assert_called_once()
    greeting_text = mock_send.call_args[0][1]
    assert "Welcome back to *Aletheia Travel*, Bob!" in greeting_text
    assert "How can I help you plan" in greeting_text


# ── 3. Web Chat Invitation Recommendation Tests ──

@patch("agentic_traveler.interfaces.routers.chat._get_chat_repo")
@patch("agentic_traveler.interfaces.routers.chat._get_orchestrator")
def test_web_chat_no_dynamic_recommendation_on_send(mock_orch, mock_get_chat_repo, client):
    """Web chat send does not dynamically append onboarding recommendation to messages anymore."""
    from agentic_traveler.interfaces.dependencies import verify_supabase_jwt, WebUserCtx
    
    app.dependency_overrides[verify_supabase_jwt] = lambda: WebUserCtx(
        user_id="web-user-uuid-123", email="test@test.com", auth_id="web-user-uuid-123"
    )
    
    mock_orch.return_value.process_request_for_user.return_value = {"text": "Sure, I can help!"}
    
    mock_repo = MagicMock()
    mock_get_chat_repo.return_value = mock_repo
    
    mock_repo.append_user_message.return_value = {
        "id": 1,
        "thread_id": "thread-123",
        "sender_type": "user",
        "sender_user_id": "web-user-uuid-123",
        "body": "Suggest a trip",
        "source": "web",
        "metadata": {},
        "created_at": "2026-06-01T12:00:00Z"
    }
    
    mock_repo.append_agent_message.side_effect = lambda uid, reply_text, source, thread_id, metadata: {
        "id": 2,
        "thread_id": "thread-123",
        "sender_type": "agent",
        "sender_user_id": "agent",
        "body": reply_text,
        "source": "web",
        "metadata": metadata,
        "created_at": "2026-06-01T12:00:00Z"
    }

    payload = {"body": "Suggest a trip"}
    try:
        resp = client.post(
            "/chat/send",
            json=payload,
        )
        assert resp.status_code == 200
        reply_body = resp.json()["reply"]["body"]
        
        assert reply_body == "Sure, I can help!"
    finally:
        app.dependency_overrides.clear()


# ── 4. Tally Webhook Merging & Processing Tests ──

@patch.dict("os.environ", {"TALLY_WEBHOOK_TOKEN": "test-tally-token"})
@patch("agentic_traveler.interfaces.routers.tally.get_db")
def test_tally_webhook_merge_with_id_token(mock_get_db, client):
    """Tally webhook with valid idToken updates the existing user and runs background profiling."""
    mock_db = MagicMock()
    mock_get_db.return_value = mock_db
    
    future = (datetime.now(timezone.utc) + timedelta(days=6)).isoformat()
    
    # 1. Token lookup (valid token in link_tokens table)
    # 2. Update existing user row in users table
    # 3. Upsert profile in user_profiles
    mock_db.table.return_value.select.return_value.eq.return_value.eq.return_value.maybe_single.return_value.execute.return_value.data = {
        "user_id": "web-user-uuid-123",
        "expires_at": future,
    }
    
    # Mock update users returning user_id
    mock_db.table.return_value.update.return_value.eq.return_value.execute.return_value.data = [{"id": "web-user-uuid-123"}]
    
    # Mock upsert user_profiles
    mock_db.table.return_value.upsert.return_value.execute.return_value.data = []
    
    # Mock token delete
    mock_db.table.return_value.delete.return_value.eq.return_value.execute.return_value = None

    tally_payload = {
        "data": {
            "responseId": "sub_999",
            "fields": [
                {"key": "question_1rxjbl", "type": "SHORT_ANSWER", "value": "Berlin"},
                {"key": "question_dPyN4N_fd3acc06-ff4d-4427-836a-64609a7985af", "type": "HIDDEN_FIELDS", "value": "tally-uuid-1"}
            ]
        }
    }

    # Patch background tasks to assert
    with patch("fastapi.BackgroundTasks.add_task") as mock_add_task:
        resp = client.post(
            "/tally-webhook",
            json=tally_payload,
            headers={"Authorization": "Bearer test-tally-token"},
        )
        
        assert resp.status_code == 200
        assert resp.json()["status"] == "ok"
        
        # Verify Background task was queued for profiling
        mock_add_task.assert_called_once()
        args = mock_add_task.call_args[0]
        assert args[1] == "web-user-uuid-123" # user_uuid
        
        # Assert update was called instead of upsert
        mock_db.table.assert_any_call("users")
        mock_db.table.return_value.update.assert_called_once_with({
            "submission_id": "sub_999",
            "location": "Berlin"
        })


@patch.dict("os.environ", {"TALLY_WEBHOOK_TOKEN": "test-tally-token"})
@patch("agentic_traveler.interfaces.routers.tally.get_db")
def test_tally_webhook_dropped_invalid_or_expired_id_token(mock_get_db, client):
    """Tally webhook with invalid or expired idToken is dropped."""
    mock_db = MagicMock()
    mock_get_db.return_value = mock_db
    
    # Token lookup returns None
    mock_db.table.return_value.select.return_value.eq.return_value.eq.return_value.maybe_single.return_value.execute.return_value.data = None

    tally_payload = {
        "data": {
            "responseId": "sub_999",
            "fields": [
                {"key": "question_1rxjbl", "type": "SHORT_ANSWER", "value": "Berlin"},
                {"key": "question_dPyN4N_fd3acc06-ff4d-4427-836a-64609a7985af", "type": "HIDDEN_FIELDS", "value": "invalid-token"}
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
    assert resp.json()["reason"] == "Invalid or expired idToken"


@patch.dict("os.environ", {"TALLY_WEBHOOK_TOKEN": "test-tally-token"})
@patch("agentic_traveler.interfaces.routers.tally.get_db")
def test_tally_webhook_merge_without_name_or_location(mock_get_db, client):
    """Tally webhook without name or location field updates only submission_id (name/location preserved)."""
    mock_db = MagicMock()
    mock_get_db.return_value = mock_db
    
    future = (datetime.now(timezone.utc) + timedelta(days=6)).isoformat()
    
    # 1. Token lookup (valid token in link_tokens table)
    mock_db.table.return_value.select.return_value.eq.return_value.eq.return_value.maybe_single.return_value.execute.return_value.data = {
        "user_id": "web-user-uuid-123",
        "expires_at": future,
    }
    
    # Mock update users returning user_id
    mock_db.table.return_value.update.return_value.eq.return_value.execute.return_value.data = [{"id": "web-user-uuid-123"}]
    
    # Mock upsert user_profiles
    mock_db.table.return_value.upsert.return_value.execute.return_value.data = []
    
    # Mock token delete
    mock_db.table.return_value.delete.return_value.eq.return_value.execute.return_value = None

    tally_payload = {
        "data": {
            "responseId": "sub_999_noname",
            "fields": [
                # Name and Location fields are entirely missing
                {"key": "question_aByWrb", "type": "SHORT_ANSWER", "value": "Solo"},
                {"key": "question_dPyN4N_fd3acc06-ff4d-4427-836a-64609a7985af", "type": "HIDDEN_FIELDS", "value": "tally-uuid-1"}
            ]
        }
    }

    # Patch background tasks to assert
    with patch("fastapi.BackgroundTasks.add_task") as mock_add_task:
        resp = client.post(
            "/tally-webhook",
            json=tally_payload,
            headers={"Authorization": "Bearer test-tally-token"},
        )
        
        assert resp.status_code == 200
        assert resp.json()["status"] == "ok"
        
        # Verify Background task was queued for profiling
        mock_add_task.assert_called_once()
        
        # Assert update was called with only submission_id, NOT name or location
        mock_db.table.assert_any_call("users")
        mock_db.table.return_value.update.assert_called_once_with({
            "submission_id": "sub_999_noname"
        })


@patch("agentic_traveler.tools.db_client.get_db")
@patch("agentic_traveler.orchestrator.profile_agent.ProfileAgent")
def test_process_background_profiling_no_credits(mock_profile_agent, mock_get_db):
    """If user has no credits, _process_background_profiling logs warning and returns early."""
    from agentic_traveler.interfaces.routers.tally import _process_background_profiling
    mock_db = MagicMock()
    mock_get_db.return_value = mock_db
    
    # Mock credit lookup returning 0 balance explicitly
    mock_db.table.return_value.select.return_value.eq.return_value.maybe_single.return_value.execute.return_value.data = {"balance": 0}
    
    _process_background_profiling("user-uuid-123", {"travel_bubble": "Solo"})
    
    # ProfileAgent should not be initialized
    mock_profile_agent.assert_not_called()


@patch("agentic_traveler.tools.db_client.get_db")
@patch("agentic_traveler.orchestrator.profile_agent.ProfileAgent")
@patch("agentic_traveler.tools.user_repo.UserRepository")
def test_process_background_profiling_has_credits(mock_user_repo, mock_profile_agent, mock_get_db):
    """If user has credits, _process_background_profiling executes completely."""
    from agentic_traveler.interfaces.routers.tally import _process_background_profiling
    mock_db = MagicMock()
    mock_get_db.return_value = mock_db
    
    # Mock credit lookup returning 500 balance explicitly
    mock_db.table.return_value.select.return_value.eq.return_value.maybe_single.return_value.execute.return_value.data = {"balance": 500}
    
    # Mock ProfileAgent build_initial_profile returning structured tags tuple
    mock_profile_agent.return_value.build_initial_profile.return_value = (
        {
            "tags": ["Solo Adventure"],
            "summary": "Likes solo travel."
        },
        None,
        0.0
    )
    
    _process_background_profiling("user-uuid-123", {"travel_bubble": "Solo"})
    
    # ProfileAgent should be initialized and build_initial_profile called with user_uuid="user-uuid-123" and token_records list
    mock_profile_agent.assert_called_once()
    mock_profile_agent.return_value.build_initial_profile.assert_called_once_with(
        {"form_response": {"travel_bubble": "Solo"}},
        user_uuid="user-uuid-123",
        token_records=ANY
    )


