"""Integration tests for Task 3: POST /api/upload endpoint."""
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

FIXTURES = Path(__file__).resolve().parent.parent / "fixtures"


@pytest.fixture
def client():
    from app.main import app
    return TestClient(app)


def test_upload_pdf_success(client: TestClient):
    """Uploading a valid PDF returns extracted data."""
    pdf_path = FIXTURES / "sample_paper.pdf"
    with open(pdf_path, "rb") as f:
        response = client.post("/api/upload", files={"file": ("paper.pdf", f, "application/pdf")})

    assert response.status_code == 200
    data = response.json()
    assert "title" in data
    assert "sections" in data
    assert data["page_count"] == 2


def test_upload_non_pdf_rejected(client: TestClient):
    """Uploading a non-PDF file returns 400."""
    response = client.post(
        "/api/upload",
        files={"file": ("readme.txt", b"hello world", "text/plain")},
    )
    assert response.status_code == 400


def test_upload_large_pdf_rejected(client: TestClient):
    """Uploading a PDF over 50 pages returns 400."""
    pdf_path = FIXTURES / "large.pdf"
    with open(pdf_path, "rb") as f:
        response = client.post("/api/upload", files={"file": ("large.pdf", f, "application/pdf")})

    assert response.status_code == 400
    assert "50" in response.json()["detail"]


def test_upload_no_file_returns_422(client: TestClient):
    """Missing file field returns 422."""
    response = client.post("/api/upload")
    assert response.status_code == 422
