"""Integration tests for Task 6: POST /api/generate SSE streaming endpoint."""
import json
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from fastapi.testclient import TestClient

FIXTURES = Path(__file__).resolve().parent.parent / "fixtures"

MOCK_ANALYSIS = {
    "title": "Attention Is All You Need",
    "summary": "Introduces the Transformer.",
    "key_algorithms": [
        {"name": "Self-Attention", "description": "...", "equations": [], "parameters": []}
    ],
    "methodology": ["Multi-head attention"],
    "data_characteristics": "Sequence data",
    "suggested_packages": ["torch", "numpy"],
    "evaluation_metrics": ["BLEU"],
}

MOCK_CELLS = [
    {"cell_type": "markdown", "source": "# Attention Is All You Need"},
    {"cell_type": "code", "source": "import torch\nimport numpy as np"},
    {"cell_type": "code", "source": "x = torch.randn(2, 3)\nprint(x)"},
]


def _make_mock_response(content: dict) -> MagicMock:
    message = MagicMock()
    message.content = json.dumps(content)
    choice = MagicMock()
    choice.message = message
    resp = MagicMock()
    resp.choices = [choice]
    return resp


@pytest.fixture
def client():
    from app.main import app
    return TestClient(app)


@patch("app.pipeline.AsyncOpenAI")
def test_generate_streams_sse_events(mock_openai_cls, client: TestClient):
    """POST /api/generate streams SSE events with status messages."""
    mock_client = MagicMock()
    mock_client.chat.completions.create = AsyncMock(
        side_effect=[
            _make_mock_response(MOCK_ANALYSIS),
            _make_mock_response({"cells": MOCK_CELLS}),
        ]
    )
    mock_openai_cls.return_value = mock_client

    pdf_path = FIXTURES / "sample_paper.pdf"
    with open(pdf_path, "rb") as f:
        response = client.post(
            "/api/generate",
            headers={"X-API-Key": "sk-test-key"},
            files={"file": ("paper.pdf", f, "application/pdf")},
        )

    assert response.status_code == 200
    assert "text/event-stream" in response.headers["content-type"]

    # Parse SSE events
    events = _parse_sse(response.text)
    assert len(events) >= 3  # At least: extracting, analyzing, generating, building, complete

    # Check that we get status events
    event_types = [e.get("event") for e in events]
    assert "status" in event_types
    assert "complete" in event_types

    # The final "complete" event should have a file_id
    complete_events = [e for e in events if e.get("event") == "complete"]
    assert len(complete_events) == 1
    complete_data = json.loads(complete_events[0]["data"])
    assert "file_id" in complete_data


@patch("app.pipeline.AsyncOpenAI")
def test_generate_creates_downloadable_notebook(mock_openai_cls):
    """After generation, the notebook can be downloaded."""
    # Use a fresh TestClient to avoid sse-starlette event loop reuse issues
    from sse_starlette.sse import AppStatus
    import asyncio
    AppStatus.should_exit_event = asyncio.Event()

    from app.main import app
    fresh_client = TestClient(app)

    mock_client = MagicMock()
    mock_client.chat.completions.create = AsyncMock(
        side_effect=[
            _make_mock_response(MOCK_ANALYSIS),
            _make_mock_response({"cells": MOCK_CELLS}),
        ]
    )
    mock_openai_cls.return_value = mock_client

    pdf_path = FIXTURES / "sample_paper.pdf"
    with open(pdf_path, "rb") as f:
        response = fresh_client.post(
            "/api/generate",
            headers={"X-API-Key": "sk-test-key"},
            files={"file": ("paper.pdf", f, "application/pdf")},
        )

    # Extract file_id from complete event
    events = _parse_sse(response.text)
    complete_data = json.loads(
        [e for e in events if e.get("event") == "complete"][0]["data"]
    )
    file_id = complete_data["file_id"]

    # Download the notebook
    dl_response = fresh_client.get(f"/api/download/{file_id}")
    assert dl_response.status_code == 200
    assert "application/octet-stream" in dl_response.headers["content-type"]


def test_generate_rejects_missing_api_key(client: TestClient):
    """Missing API key returns 400."""
    pdf_path = FIXTURES / "sample_paper.pdf"
    with open(pdf_path, "rb") as f:
        response = client.post(
            "/api/generate",
            files={"file": ("paper.pdf", f, "application/pdf")},
        )
    assert response.status_code == 400


def test_generate_rejects_non_pdf(client: TestClient):
    """Non-PDF file returns 400."""
    response = client.post(
        "/api/generate",
        headers={"X-API-Key": "sk-test-key"},
        files={"file": ("readme.txt", b"hello", "text/plain")},
    )
    assert response.status_code == 400


def test_download_nonexistent_returns_404(client: TestClient):
    """Downloading a non-existent file returns 404."""
    response = client.get("/api/download/nonexistent-id")
    assert response.status_code == 404


def _parse_sse(text: str) -> list[dict]:
    """Parse SSE text into a list of event dicts."""
    events = []
    current: dict = {}
    for line in text.split("\n"):
        line = line.strip()  # Handle \r\n line endings
        if line.startswith("event:"):
            current["event"] = line[len("event:"):].strip()
        elif line.startswith("data:"):
            current["data"] = line[len("data:"):].strip()
        elif line == "" and current:
            events.append(current)
            current = {}
    if current:
        events.append(current)
    return events
