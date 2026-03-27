"""Integration tests for Task 8: Open in Colab functionality."""
import json
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch
from urllib.parse import quote_plus

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
    "suggested_packages": ["torch"],
    "evaluation_metrics": ["BLEU"],
}

MOCK_CELLS = [
    {"cell_type": "markdown", "source": "# Attention Is All You Need"},
    {"cell_type": "code", "source": "import torch"},
]


def _make_mock_response(content: dict) -> MagicMock:
    message = MagicMock()
    message.content = json.dumps(content)
    choice = MagicMock()
    choice.message = message
    resp = MagicMock()
    resp.choices = [choice]
    return resp


def _parse_sse(text: str) -> list[dict]:
    events = []
    current = {}
    for line in text.split("\n"):
        line = line.strip()
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


@pytest.fixture
def client():
    from sse_starlette.sse import AppStatus
    import asyncio
    AppStatus.should_exit_event = asyncio.Event()
    from app.main import app
    return TestClient(app)


@patch("app.pipeline.AsyncOpenAI")
def test_complete_event_includes_colab_url(mock_openai_cls, client: TestClient):
    """The 'complete' SSE event includes a colab_url field."""
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

    events = _parse_sse(response.text)
    complete_events = [e for e in events if e.get("event") == "complete"]
    assert len(complete_events) == 1

    complete_data = json.loads(complete_events[0]["data"])
    assert "colab_url" in complete_data
    assert "colab.research.google.com" in complete_data["colab_url"]
    assert complete_data["file_id"] in complete_data["colab_url"]


def test_notebook_endpoint_serves_ipynb(client: TestClient):
    """The /api/notebook/{file_id} endpoint serves the notebook with correct content-type for Colab."""
    # First create a notebook via the generated dir
    from app.main import GENERATED_DIR
    import nbformat

    nb = nbformat.v4.new_notebook()
    nb.cells.append(nbformat.v4.new_code_cell("print('hello')"))
    test_id = "test-colab-notebook"
    path = GENERATED_DIR / f"{test_id}.ipynb"
    path.write_text(nbformat.writes(nb))

    try:
        response = client.get(f"/api/notebook/{test_id}")
        assert response.status_code == 200
        assert "application/json" in response.headers["content-type"]
        # Verify it's valid JSON (Colab needs this)
        data = response.json()
        assert "cells" in data
    finally:
        path.unlink(missing_ok=True)
