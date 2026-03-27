"""Integration tests for Task 1: Project setup — FastAPI backend with static file serving."""
import pytest
from fastapi.testclient import TestClient


@pytest.fixture
def client():
    from app.main import app
    return TestClient(app)


def test_health_check(client: TestClient):
    """Health check endpoint returns 200 with status ok."""
    response = client.get("/api/health")
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "ok"


def test_static_index_served(client: TestClient):
    """Root path serves the static index.html."""
    response = client.get("/")
    assert response.status_code == 200
    assert "text/html" in response.headers["content-type"]
    assert "Paper-to-Notebook" in response.text


def test_cors_headers(client: TestClient):
    """CORS headers are present on API responses."""
    response = client.options(
        "/api/health",
        headers={
            "Origin": "http://localhost:3000",
            "Access-Control-Request-Method": "GET",
        },
    )
    assert response.status_code == 200
    assert "access-control-allow-origin" in response.headers
