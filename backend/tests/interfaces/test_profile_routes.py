"""Task 54 — /profile/answer endpoint: server-side validation + write delegation.

Calls the route handler directly (no TestClient) and monkeypatches the write +
metric so no DB / Gemini is touched.
"""

import asyncio

import pytest
from fastapi import HTTPException

from agentic_traveler.interfaces import schemas
from agentic_traveler.interfaces.dependencies import WebUserCtx
from agentic_traveler.interfaces.routers import profile as profile_router


def _ctx():
    return WebUserCtx(user_id="u1", auth_id="a1")


def _run(coro):
    return asyncio.run(coro)


def test_answer_happy_path_writes(monkeypatch):
    calls: list = []
    monkeypatch.setattr(
        profile_router, "apply_profile_patch", lambda uid, payload: calls.append((uid, payload))
    )
    monkeypatch.setattr(profile_router, "emit_metric_now", lambda *a, **k: None)

    payload = schemas.ProfileAnswerIn(qid="travel_company", values=["duo"])
    out = _run(profile_router.profile_answer(payload, ctx=_ctx()))

    assert out.qid == "travel_company" and out.value == "duo"
    assert calls == [
        ("u1", {"qid": "travel_company", "value": "duo", "source": "chat_tap"})
    ]


def test_answer_illegal_value_422_no_write(monkeypatch):
    calls: list = []
    monkeypatch.setattr(
        profile_router, "apply_profile_patch", lambda uid, payload: calls.append(1)
    )
    monkeypatch.setattr(profile_router, "emit_metric_now", lambda *a, **k: None)

    payload = schemas.ProfileAnswerIn(qid="travel_company", values=["spaceship"])
    with pytest.raises(HTTPException) as ei:
        _run(profile_router.profile_answer(payload, ctx=_ctx()))

    assert ei.value.status_code == 422
    assert calls == []


def test_answer_unknown_qid_422(monkeypatch):
    monkeypatch.setattr(profile_router, "apply_profile_patch", lambda uid, payload: None)
    monkeypatch.setattr(profile_router, "emit_metric_now", lambda *a, **k: None)

    payload = schemas.ProfileAnswerIn(qid="nope", values=["x"])
    with pytest.raises(HTTPException) as ei:
        _run(profile_router.profile_answer(payload, ctx=_ctx()))

    assert ei.value.status_code == 422
