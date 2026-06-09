"""SSE streaming endpoint /chat/stream (Task 37).

Builds a minimal app with only the chat router so we don't import the
env-sensitive Telegram router. The orchestrator and chat repo are mocked — no
DB / LLM. Asserts the SSE event ordering: status… → delta… → done.
"""

from types import SimpleNamespace
from unittest.mock import MagicMock, patch

from fastapi import FastAPI
from fastapi.testclient import TestClient

from agentic_traveler.interfaces.dependencies import verify_supabase_jwt
from agentic_traveler.interfaces.routers import chat as chat_router


def _parse_events(body: str):
    """Parse raw SSE text into a list of (event, data_str) tuples."""
    events = []
    for frame in body.strip().split("\n\n"):
        if not frame.strip():
            continue
        event, data = None, None
        for line in frame.splitlines():
            if line.startswith("event:"):
                event = line[len("event:"):].strip()
            elif line.startswith("data:"):
                data = line[len("data:"):].strip()
        if event:
            events.append((event, data))
    return events


def _make_client(orch, repo):
    app = FastAPI()
    app.include_router(chat_router.router)
    app.dependency_overrides[verify_supabase_jwt] = lambda: SimpleNamespace(user_id="u1")
    return TestClient(app)


def _repo():
    repo = MagicMock()
    repo.append_user_message.return_value = {"thread_id": "thread-1", "id": 1}
    repo.append_agent_message.return_value = {"id": 42, "thread_id": "thread-1"}
    return repo


def test_stream_emits_status_then_delta_then_done():
    def fake_process(user_id, body, status_callback, delta_callback):
        status_callback({"phase": "router", "text": "Understanding what you're asking…"})
        status_callback({"phase": "saga_selected", "saga": "PlanningSaga", "text": "Picking up your trip…"})
        delta_callback({"text": "Iceland in late "})
        delta_callback({"text": "January is magical."})
        return {"text": "Iceland in late January is magical.", "action": "RESPONSE"}

    orch = MagicMock()
    orch.process_request_for_user.side_effect = fake_process
    repo = _repo()

    with patch.object(chat_router, "_get_orchestrator", return_value=orch), \
         patch.object(chat_router, "_get_chat_repo", return_value=repo):
        client = _make_client(orch, repo)
        resp = client.post("/chat/stream", json={"body": "plan iceland"})

    assert resp.status_code == 200
    assert resp.headers["content-type"].startswith("text/event-stream")
    events = _parse_events(resp.text)
    names = [e for e, _ in events]

    assert "status" in names
    assert "delta" in names
    assert names[-1] == "done"
    # Ordering: all statuses precede the first delta; done is last.
    first_delta = names.index("delta")
    assert all(n == "status" for n in names[:first_delta])
    # done carries the persisted message_id.
    done_data = events[-1][1]
    assert '"message_id": 42' in done_data
    # The reply text is delivered across the delta chunks.
    delta_text = "".join(
        d.split('"text":', 1)[1] for e, d in events if e == "delta"
    )
    assert "Iceland" in delta_text
    repo.append_user_message.assert_called_once()
    repo.append_agent_message.assert_called_once()


def test_stream_persists_reply_before_streaming_for_recovery():
    # The agent reply must be persisted (so Realtime can recover it) even though
    # the deltas stream afterwards.
    def fake_process(user_id, body, status_callback, delta_callback):
        return {"text": "Hello there", "action": "RESPONSE"}

    orch = MagicMock()
    orch.process_request_for_user.side_effect = fake_process
    repo = _repo()

    with patch.object(chat_router, "_get_orchestrator", return_value=orch), \
         patch.object(chat_router, "_get_chat_repo", return_value=repo):
        client = _make_client(orch, repo)
        resp = client.post("/chat/stream", json={"body": "hi"})

    assert resp.status_code == 200
    repo.append_agent_message.assert_called_once()
    kwargs = repo.append_agent_message.call_args.kwargs
    assert kwargs.get("source") == "web"
    assert kwargs.get("thread_id") == "thread-1"


def test_stream_orchestrator_failure_emits_error_status_and_still_closes():
    orch = MagicMock()
    orch.process_request_for_user.side_effect = RuntimeError("boom")
    repo = _repo()

    with patch.object(chat_router, "_get_orchestrator", return_value=orch), \
         patch.object(chat_router, "_get_chat_repo", return_value=repo):
        client = _make_client(orch, repo)
        resp = client.post("/chat/stream", json={"body": "hi"})

    assert resp.status_code == 200
    events = _parse_events(resp.text)
    names = [e for e, _ in events]
    assert names[-1] == "done"          # stream still closes cleanly
    assert any(e == "status" and d and "error" in d for e, d in events)
    # A fallback reply is still persisted.
    repo.append_agent_message.assert_called_once()


def test_stream_rejects_empty_body():
    orch = MagicMock()
    repo = _repo()
    with patch.object(chat_router, "_get_orchestrator", return_value=orch), \
         patch.object(chat_router, "_get_chat_repo", return_value=repo):
        client = _make_client(orch, repo)
        resp = client.post("/chat/stream", json={"body": "   "})
    assert resp.status_code == 400
