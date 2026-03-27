"""Comprehensive integration tests for v3 Task 2 — covering API gaps."""
import asyncio
import json
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from fastapi.testclient import TestClient

FIXTURES = Path(__file__).resolve().parent.parent / "fixtures"

MOCK_ANALYSIS = {
    "title": "Test Paper", "summary": "Test", "key_algorithms": [
        {"name": "Algo1", "description": "d", "equations": [], "parameters": []}
    ],
    "methodology": ["M1"], "data_characteristics": "", "suggested_packages": ["numpy"],
    "evaluation_metrics": ["acc"],
}
MOCK_CELLS = [
    {"cell_type": "markdown", "source": "# Title"},
    {"cell_type": "code", "source": "import numpy as np\nprint('hello')"},
]


def _mock_resp(content):
    m = MagicMock()
    m.content = json.dumps(content)
    c = MagicMock()
    c.message = m
    r = MagicMock()
    r.choices = [c]
    return r


def _parse_sse(text):
    events = []
    current = {}
    for line in text.split("\n"):
        line = line.strip()
        if line.startswith("event:"):
            current["event"] = line[6:].strip()
        elif line.startswith("data:"):
            current["data"] = line[5:].strip()
        elif line == "" and current:
            events.append(current)
            current = {}
    if current:
        events.append(current)
    return events


@pytest.fixture
def client():
    from sse_starlette.sse import AppStatus
    AppStatus.should_exit_event = asyncio.Event()
    from app.main import app
    return TestClient(app)


# ── Upload endpoint comprehensive ────────────────────────

def test_upload_real_sample_pdf(client: TestClient):
    """Upload the sample paper fixture and verify extraction fields."""
    pdf_path = FIXTURES / "sample_paper.pdf"
    with open(pdf_path, "rb") as f:
        response = client.post("/api/upload", files={"file": ("paper.pdf", f, "application/pdf")})
    assert response.status_code == 200
    data = response.json()
    assert "title" in data
    assert "full_text" in data
    assert "sections" in data
    assert data["page_count"] >= 1


def test_upload_two_column_pdf(client: TestClient):
    """Upload a two-column PDF and verify both columns extracted."""
    pdf_path = FIXTURES / "two_column.pdf"
    with open(pdf_path, "rb") as f:
        response = client.post("/api/upload", files={"file": ("two_col.pdf", f, "application/pdf")})
    assert response.status_code == 200
    text = response.json()["full_text"]
    assert "left column" in text.lower()
    assert "right column" in text.lower()


def test_upload_numbered_sections_pdf(client: TestClient):
    """Upload a PDF with numbered sections and verify detection."""
    pdf_path = FIXTURES / "numbered_sections.pdf"
    with open(pdf_path, "rb") as f:
        response = client.post("/api/upload", files={"file": ("num.pdf", f, "application/pdf")})
    assert response.status_code == 200
    headings = [s["heading"] for s in response.json()["sections"]]
    assert any("Introduction" in h for h in headings)


# ── Generate + Download + Notebook JSON flow ─────────────

@patch("app.pipeline.AsyncOpenAI")
def test_generate_then_download_valid_ipynb(mock_cls, client: TestClient):
    """Full flow: generate → download → valid .ipynb."""
    mock_client = MagicMock()
    mock_client.chat.completions.create = AsyncMock(
        side_effect=[_mock_resp(MOCK_ANALYSIS), _mock_resp({"cells": MOCK_CELLS})]
    )
    mock_cls.return_value = mock_client

    pdf_path = FIXTURES / "sample_paper.pdf"
    with open(pdf_path, "rb") as f:
        resp = client.post(
            "/api/generate",
            headers={"X-API-Key": "sk-test"},
            files={"file": ("paper.pdf", f, "application/pdf")},
        )
    assert resp.status_code == 200
    events = _parse_sse(resp.text)
    complete = [e for e in events if e.get("event") == "complete"]
    assert len(complete) == 1
    file_id = json.loads(complete[0]["data"])["file_id"]

    # Download
    dl = client.get(f"/api/download/{file_id}")
    assert dl.status_code == 200
    import nbformat
    nb = nbformat.reads(dl.content.decode("utf-8"), as_version=4)
    nbformat.validate(nb)

    # Notebook JSON endpoint
    nj = client.get(f"/api/notebook/{file_id}")
    assert nj.status_code == 200
    assert "cells" in nj.json()


# ── Security headers on different response types ─────────

def test_security_headers_on_404(client: TestClient):
    """Security headers present even on 404 responses."""
    resp = client.get("/api/download/nonexistent")
    assert resp.status_code == 404
    assert "X-Content-Type-Options" in resp.headers
    assert "X-Frame-Options" in resp.headers


def test_security_headers_on_400(client: TestClient):
    """Security headers present on 400 validation errors."""
    resp = client.post("/api/upload", files={"file": ("bad.txt", b"hi", "text/plain")})
    assert resp.status_code == 400
    assert "X-Content-Type-Options" in resp.headers


def test_security_headers_on_sse(client: TestClient):
    """Security headers present on SSE streaming responses."""
    pdf_path = FIXTURES / "sample_paper.pdf"
    with open(pdf_path, "rb") as f:
        resp = client.post(
            "/api/generate",
            headers={"X-API-Key": "sk-test"},
            files={"file": ("paper.pdf", f, "application/pdf")},
        )
    # Even SSE responses get security headers
    assert "X-Content-Type-Options" in resp.headers


# ── CORS preflight ───────────────────────────────────────

def test_cors_preflight_post_generate(client: TestClient):
    """CORS preflight for POST /api/generate works."""
    resp = client.options(
        "/api/generate",
        headers={
            "Origin": "http://localhost:8000",
            "Access-Control-Request-Method": "POST",
            "Access-Control-Request-Headers": "X-API-Key,Content-Type",
        },
    )
    assert resp.status_code == 200
    assert "access-control-allow-origin" in resp.headers


def test_cors_rejects_unknown_origin(client: TestClient):
    """CORS rejects requests from unknown origins."""
    resp = client.options(
        "/api/health",
        headers={
            "Origin": "https://evil.com",
            "Access-Control-Request-Method": "GET",
        },
    )
    # Should not include the evil origin in allow-origin
    allowed = resp.headers.get("access-control-allow-origin", "")
    assert "evil.com" not in allowed


# ── History endpoint after operations ────────────────────

def test_history_empty_without_session(client: TestClient):
    """History returns empty list without session cookie."""
    resp = client.get("/api/history")
    assert resp.status_code == 200
    assert resp.json() == []
