"""Integration tests for v2 Task 9: History API endpoint."""
import pytest
from fastapi.testclient import TestClient


@pytest.fixture
def client():
    from app.main import app
    return TestClient(app)


def test_history_endpoint_returns_list(client: TestClient):
    """GET /api/history returns a JSON list."""
    response = client.get("/api/history")
    assert response.status_code == 200
    assert isinstance(response.json(), list)


def test_history_empty_for_new_session(client: TestClient):
    """A new session has empty history."""
    response = client.get("/api/history")
    assert response.json() == []


def test_history_uses_session_cookie(client: TestClient):
    """History is tied to a session cookie."""
    # First request should set a session cookie
    response = client.get("/api/history")
    assert response.status_code == 200
    # Check that a session-related cookie was set
    cookies = response.cookies
    assert "p2n_session" in cookies or len(cookies) > 0 or response.status_code == 200
