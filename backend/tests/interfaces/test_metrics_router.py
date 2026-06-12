"""Metrics ingestion router tests (Task 50) — allowlist + auth boundary.

The Supabase JWT dependency is overridden; emit_metric_now is patched (no DB).
"""

from unittest.mock import patch

import pytest
from fastapi.testclient import TestClient

with patch("agentic_traveler.interfaces.routers.telegram.UserRepository"), \
     patch("agentic_traveler.interfaces.routers.telegram.OrchestratorAgent"):
    from agentic_traveler.interfaces.main import app

from agentic_traveler.interfaces.dependencies import WebUserCtx, verify_supabase_jwt


@pytest.fixture
def client():
    app.dependency_overrides[verify_supabase_jwt] = lambda: WebUserCtx(
        user_id="u1", auth_id="u1"
    )
    with TestClient(app) as c:
        yield c
    app.dependency_overrides.clear()


def test_known_metric_recorded(client):
    with patch("agentic_traveler.interfaces.routers.metrics.emit_metric_now") as emit:
        resp = client.post("/metrics/event", json={
            "name": "capability_launched",
            "props": {"id": "plan_a_trip", "kind": "message", "surface": "sheet"},
        })
    assert resp.status_code == 200
    emit.assert_called_once()
    assert emit.call_args.args[0] == "capability_launched"
    assert emit.call_args.kwargs["user_id"] == "u1"
    assert emit.call_args.kwargs["payload"]["id"] == "plan_a_trip"


def test_unknown_metric_rejected_422(client):
    """Allowlist is the trust boundary — arbitrary names can't write rows."""
    with patch("agentic_traveler.interfaces.routers.metrics.emit_metric_now") as emit:
        resp = client.post("/metrics/event", json={"name": "evil_event", "props": {}})
    assert resp.status_code == 422
    emit.assert_not_called()
