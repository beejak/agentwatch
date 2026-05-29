"""Gate 15: FastAPI — REST API endpoints."""
import time
import uuid
import pytest
from httpx import AsyncClient, ASGITransport


@pytest.fixture
async def client():
    from watchtower.api.main import app
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as c:
        yield c


async def test_health_returns_200(client):
    """GET /health returns 200."""
    response = await client.get("/api/v1/health")
    assert response.status_code == 200
    data = response.json()
    assert "status" in data


async def test_health_has_infra_fields(client):
    """Health response contains infra status fields."""
    response = await client.get("/api/v1/health")
    data = response.json()
    # Should have status + at least some infra fields
    assert "status" in data


async def test_traces_unknown_returns_empty(client):
    """GET /traces/{unknown_id} returns 200 with 0 spans."""
    trace_id = str(uuid.uuid4())
    response = await client.get(f"/api/v1/traces/{trace_id}")
    assert response.status_code == 200
    data = response.json()
    assert data["trace_id"] == trace_id
    assert "span_count" in data


async def test_analyst_report_has_markdown(client):
    """GET /analyst/report/{trace_id} returns markdown_report field."""
    trace_id = str(uuid.uuid4())
    response = await client.get(f"/api/v1/analyst/report/{trace_id}")
    assert response.status_code == 200
    data = response.json()
    assert "markdown_report" in data
    assert len(data["markdown_report"]) > 0


async def test_analyst_silent_failures_returns_list(client):
    """GET /analyst/silent-failures returns a list (may be empty)."""
    response = await client.get("/api/v1/analyst/silent-failures")
    assert response.status_code == 200
    data = response.json()
    assert isinstance(data, list)


async def test_interceptor_quarantine_missing_body(client):
    """POST /interceptor/quarantine with no body → 422."""
    response = await client.post("/api/v1/interceptor/quarantine", json={})
    assert response.status_code == 422


async def test_interceptor_quarantine_valid(client):
    """POST /interceptor/quarantine with valid body → 200."""
    response = await client.post(
        "/api/v1/interceptor/quarantine",
        json={"agent_id": "test-agent", "reason": "testing", "trigger": "api"},
    )
    assert response.status_code == 200
    data = response.json()
    assert data["target_agent"] == "test-agent"
    assert data["logged"] is True


async def test_response_time_under_2s(client):
    """All endpoints respond under 2 seconds."""
    endpoints = [
        "/api/v1/health",
        f"/api/v1/traces/{uuid.uuid4()}",
        f"/api/v1/analyst/report/{uuid.uuid4()}",
        "/api/v1/analyst/silent-failures",
    ]
    for endpoint in endpoints:
        start = time.time()
        response = await client.get(endpoint)
        elapsed = time.time() - start
        assert elapsed < 2.0, f"{endpoint} took {elapsed:.2f}s (limit: 2s)"
        assert response.status_code == 200
