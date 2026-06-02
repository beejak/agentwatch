"""Security tests — API authentication and authorization."""
from __future__ import annotations

import os

import pytest
from fastapi.testclient import TestClient


@pytest.fixture(scope="module")
def client():
    from watchtower.api.main import app
    return TestClient(app)


def test_quarantine_no_key_when_env_unset(client):
    """When WATCHTOWER_API_KEY is not set, quarantine is open (dev mode)."""
    # Ensure env is unset
    os.environ.pop("WATCHTOWER_API_KEY", None)
    resp = client.post("/api/v1/interceptor/quarantine", json={
        "agent_id": "test-agent",
        "reason": "security test",
        "trigger": "test",
    })
    assert resp.status_code == 200


def test_quarantine_requires_key_when_env_set(client, monkeypatch):
    """When WATCHTOWER_API_KEY is set, missing key returns 403."""
    import watchtower.api.routers.interceptor as mod
    monkeypatch.setattr(mod, "_WATCHTOWER_KEY", "secret-key-123")
    resp = client.post("/api/v1/interceptor/quarantine", json={
        "agent_id": "test-agent",
        "reason": "test",
        "trigger": "test",
    })
    assert resp.status_code == 403


def test_quarantine_valid_key_passes(client, monkeypatch):
    """Correct API key allows quarantine."""
    import watchtower.api.routers.interceptor as mod
    monkeypatch.setattr(mod, "_WATCHTOWER_KEY", "secret-key-123")
    resp = client.post(
        "/api/v1/interceptor/quarantine",
        json={"agent_id": "test-agent", "reason": "test", "trigger": "test"},
        headers={"X-WatchTower-Key": "secret-key-123"},
    )
    assert resp.status_code == 200


def test_quarantine_wrong_key_rejected(client, monkeypatch):
    """Wrong API key returns 403."""
    import watchtower.api.routers.interceptor as mod
    monkeypatch.setattr(mod, "_WATCHTOWER_KEY", "secret-key-123")
    resp = client.post(
        "/api/v1/interceptor/quarantine",
        json={"agent_id": "test-agent", "reason": "test", "trigger": "test"},
        headers={"X-WatchTower-Key": "wrong-key"},
    )
    assert resp.status_code == 403


def test_verdicts_limit_rejected_over_1000(client):
    """limit > 1000 must be rejected with 422."""
    resp = client.get("/api/v1/agents/agent-x/verdicts?limit=99999")
    assert resp.status_code == 422


def test_verdicts_limit_1000_accepted(client):
    """limit == 1000 is the maximum allowed."""
    resp = client.get("/api/v1/agents/agent-x/verdicts?limit=1000")
    assert resp.status_code == 200


def test_verdicts_limit_0_rejected(client):
    """limit == 0 (below minimum of 1) is rejected."""
    resp = client.get("/api/v1/agents/agent-x/verdicts?limit=0")
    assert resp.status_code == 422


def test_health_endpoint_no_auth_required(client):
    """Health endpoint must be public."""
    resp = client.get("/api/v1/health")
    assert resp.status_code == 200
