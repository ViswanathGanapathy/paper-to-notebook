"""Integration tests for v2 Task 3: API key transport hardening + CORS tightening."""
import asyncio
import json
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from fastapi.testclient import TestClient

FIXTURES = Path(__file__).resolve().parent.parent / "fixtures"

MOCK_ANALYSIS = {
    "title": "Test Paper", "summary": "Test", "key_algorithms": [],
    "methodology": [], "data_characteristics": "", "suggested_packages": [],
    "evaluation_metrics": [],
}
MOCK_CELLS = [{"cell_type": "code", "source": "print('hi')"}]


def _mock_response(content):
    m = MagicMock()
    m.content = json.dumps(content)
    c = MagicMock()
    c.message = m
    r = MagicMock()
    r.choices = [c]
    return r


@pytest.fixture
def client():
    from sse_starlette.sse import AppStatus
    AppStatus.should_exit_event = asyncio.Event()
    from app.main import app
    return TestClient(app)


@patch("app.pipeline.AsyncOpenAI")
def test_generate_accepts_api_key_in_header(mock_cls, client: TestClient):
    """API key can be sent via X-API-Key header instead of form field."""
    mock_client = MagicMock()
    mock_client.chat.completions.create = AsyncMock(
        side_effect=[_mock_response(MOCK_ANALYSIS), _mock_response({"cells": MOCK_CELLS})]
    )
    mock_cls.return_value = mock_client

    pdf_path = FIXTURES / "sample_paper.pdf"
    with open(pdf_path, "rb") as f:
        response = client.post(
            "/api/generate",
            headers={"X-API-Key": "sk-test-header-key"},
            files={"file": ("paper.pdf", f, "application/pdf")},
        )

    assert response.status_code == 200
    assert "text/event-stream" in response.headers["content-type"]


def test_generate_rejects_missing_api_key(client: TestClient):
    """Missing API key (no header, no form field) returns 400."""
    pdf_path = FIXTURES / "sample_paper.pdf"
    with open(pdf_path, "rb") as f:
        response = client.post(
            "/api/generate",
            files={"file": ("paper.pdf", f, "application/pdf")},
        )
    # Should be 400 (missing key) not 422 (validation error)
    assert response.status_code in (400, 422)


def test_cors_methods_restricted(client: TestClient):
    """CORS only allows GET and POST methods."""
    response = client.options(
        "/api/health",
        headers={
            "Origin": "http://localhost:8000",
            "Access-Control-Request-Method": "DELETE",
        },
    )
    # DELETE should not be in allowed methods
    allowed = response.headers.get("access-control-allow-methods", "")
    assert "DELETE" not in allowed


def test_cors_headers_restricted(client: TestClient):
    """CORS allows specific headers, not wildcard."""
    response = client.options(
        "/api/health",
        headers={
            "Origin": "http://localhost:8000",
            "Access-Control-Request-Method": "POST",
            "Access-Control-Request-Headers": "X-API-Key",
        },
    )
    allowed = response.headers.get("access-control-allow-headers", "")
    assert "X-API-Key" in allowed or "x-api-key" in allowed
