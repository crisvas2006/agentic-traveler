"""Web chat router tests (Task 43) — metadata.ui shaping + selection passthrough.

The Supabase JWT dependency is overridden; the orchestrator and ChatRepository
are mocked (no DB / LLM).
"""

from unittest.mock import MagicMock, patch

import pytest
from fastapi.testclient import TestClient

with patch("agentic_traveler.interfaces.routers.telegram.UserRepository"), \
     patch("agentic_traveler.interfaces.routers.telegram.OrchestratorAgent"):
    from agentic_traveler.interfaces.main import app

from agentic_traveler.interfaces.dependencies import WebUserCtx, verify_supabase_jwt
from agentic_traveler.interfaces.routers import chat as chat_router


@pytest.fixture
def client():
    app.dependency_overrides[verify_supabase_jwt] = lambda: WebUserCtx(
        user_id="u1", auth_id="u1"
    )
    with TestClient(app) as c:
        yield c
    app.dependency_overrides.clear()


def _fake_repo():
    repo = MagicMock()

    def append_user(user_id, body, source, thread_id=None):
        return {
            "id": 1, "thread_id": "t1", "sender_type": "user",
            "sender_user_id": user_id, "body": body, "source": source,
            "metadata": {}, "created_at": "2026-01-01T00:00:00Z",
        }

    def append_agent(user_id, body, source, thread_id=None, metadata=None):
        return {
            "id": 2, "thread_id": "t1", "sender_type": "agent",
            "sender_user_id": None, "body": body, "source": source,
            "metadata": metadata or {}, "created_at": "2026-01-01T00:00:01Z",
        }

    repo.append_user_message.side_effect = append_user
    repo.append_agent_message.side_effect = append_agent
    return repo


def _orch(result):
    orch = MagicMock()
    orch.process_request_for_user.return_value = result
    return orch


_PACE_SLOT_REQUEST = {
    "slot": "pace", "prompt": "What pace feels right?", "allow_multi": False,
    "choices": [
        {"id": "slow", "label": "Slow", "value": "slow"},
        {"id": "skip", "label": "Skip", "value": "skip"},
    ],
}


def test_send_writes_multi_choice_ui_block(client):
    repo = _fake_repo()
    orch = _orch({
        "text": "What pace feels right?", "action": "RESPONSE",
        "slot_request": _PACE_SLOT_REQUEST,
    })
    with patch.object(chat_router, "_get_chat_repo", return_value=repo), \
         patch.object(chat_router, "_get_orchestrator", return_value=orch):
        resp = client.post("/chat/send", json={"body": "plan a trip to Iceland"})
    assert resp.status_code == 200
    ui = resp.json()["reply"]["metadata"]["ui"]
    assert ui["kind"] == "multi_choice"
    assert ui["slot"] == "pace"
    assert {o["id"] for o in ui["options"]} == {"slow", "skip"}


def test_send_without_choices_leaves_ui_unset(client):
    repo = _fake_repo()
    orch = _orch({"text": "Sure!", "action": "RESPONSE", "slot_request": None})
    with patch.object(chat_router, "_get_chat_repo", return_value=repo), \
         patch.object(chat_router, "_get_orchestrator", return_value=orch):
        resp = client.post("/chat/send", json={"body": "hi"})
    assert resp.status_code == 200
    assert "ui" not in resp.json()["reply"]["metadata"]


def test_send_selection_passes_through_and_persists_label(client):
    repo = _fake_repo()
    orch = _orch({
        "text": "How structured do you want it?", "action": "RESPONSE",
        "slot_request": {
            "slot": "structure", "prompt": "How structured?", "allow_multi": False,
            "choices": [{"id": "loose", "label": "Loose", "value": "loose"}],
        },
    })
    with patch.object(chat_router, "_get_chat_repo", return_value=repo), \
         patch.object(chat_router, "_get_orchestrator", return_value=orch):
        resp = client.post("/chat/send", json={
            "body": "Slow — room to breathe",
            "selection": {"slot": "pace", "values": ["slow"]},
        })
    assert resp.status_code == 200
    # The structured selection reached the orchestrator.
    kwargs = orch.process_request_for_user.call_args.kwargs
    assert kwargs["selection"] == {"slot": "pace", "values": ["slow"]}
    # The chosen label is the persisted user-message body (shown in the bubble).
    assert resp.json()["user_message"]["body"] == "Slow — room to breathe"
    # The next prompt's chips ride back on the reply.
    assert resp.json()["reply"]["metadata"]["ui"]["slot"] == "structure"
