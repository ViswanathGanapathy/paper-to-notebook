"""Integration tests for v2 Task 2: Rate limiting on expensive endpoints."""
import asyncio
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

FIXTURES = Path(__file__).resolve().parent.parent / "fixtures"


def _fresh_client():
    """Create a fresh client with reset rate limiter and SSE state."""
    from sse_starlette.sse import AppStatus
    AppStatus.should_exit_event = asyncio.Event()
    from app.security import limiter
    limiter.reset()
    from app.main import app
    return TestClient(app)


@pytest.fixture
def client():
    return _fresh_client()


def test_generate_rate_limited():
    """/api/generate returns 429 after exceeding 5 requests/minute."""
    client = _fresh_client()
    pdf_path = FIXTURES / "sample_paper.pdf"

    for i in range(5):
        # Reset SSE state for each request to avoid event loop issues
        from sse_starlette.sse import AppStatus
        AppStatus.should_exit_event = asyncio.Event()

        with open(pdf_path, "rb") as f:
            response = client.post(
                "/api/generate",
                headers={"X-API-Key": "sk-test-key"},
                files={"file": ("paper.pdf", f, "application/pdf")},
            )
        assert response.status_code != 429, f"Request {i+1} should not be rate limited"

    # The 6th request should be rate limited
    with open(pdf_path, "rb") as f:
        response = client.post(
            "/api/generate",
            headers={"X-API-Key": "sk-test-key"},
            files={"file": ("paper.pdf", f, "application/pdf")},
        )
    assert response.status_code == 429


def test_upload_rate_limited(client: TestClient):
    """/api/upload returns 429 after exceeding 20 requests/minute."""
    pdf_path = FIXTURES / "sample_paper.pdf"

    for i in range(20):
        with open(pdf_path, "rb") as f:
            client.post("/api/upload", files={"file": ("paper.pdf", f, "application/pdf")})

    # The 21st request should be rate limited
    with open(pdf_path, "rb") as f:
        response = client.post("/api/upload", files={"file": ("paper.pdf", f, "application/pdf")})
    assert response.status_code == 429


def test_health_not_quickly_limited(client: TestClient):
    """/api/health has generous rate limits."""
    for _ in range(30):
        response = client.get("/api/health")
        assert response.status_code == 200


def test_rate_limit_returns_clear_message():
    """Rate limit response includes a helpful error message."""
    client = _fresh_client()
    pdf_path = FIXTURES / "sample_paper.pdf"

    for _ in range(5):
        from sse_starlette.sse import AppStatus
        AppStatus.should_exit_event = asyncio.Event()
        with open(pdf_path, "rb") as f:
            client.post(
                "/api/generate",
                headers={"X-API-Key": "sk-test-key"},
                files={"file": ("paper.pdf", f, "application/pdf")},
            )

    with open(pdf_path, "rb") as f:
        response = client.post(
            "/api/generate",
            headers={"X-API-Key": "sk-test-key"},
            files={"file": ("paper.pdf", f, "application/pdf")},
        )
    assert response.status_code == 429
    body = response.json()
    assert "rate" in body.get("detail", "").lower() or "limit" in body.get("detail", "").lower() or "error" in body.get("error", "").lower()
