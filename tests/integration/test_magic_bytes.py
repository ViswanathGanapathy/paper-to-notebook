"""Integration tests for v2 Task 4: Magic byte validation at API level."""
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

FIXTURES = Path(__file__).resolve().parent.parent / "fixtures"


@pytest.fixture
def client():
    from app.main import app
    return TestClient(app)


def test_upload_rejects_non_pdf_magic_bytes(client: TestClient):
    """Uploading a file with .pdf extension but non-PDF content returns 400."""
    fake_pdf = b"<!DOCTYPE html><html><body>not a pdf</body></html>"
    response = client.post(
        "/api/upload",
        files={"file": ("fake.pdf", fake_pdf, "application/pdf")},
    )
    assert response.status_code == 400
    assert "valid PDF" in response.json()["detail"]


def test_upload_accepts_real_pdf(client: TestClient):
    """Uploading a real PDF with correct magic bytes works."""
    pdf_path = FIXTURES / "sample_paper.pdf"
    with open(pdf_path, "rb") as f:
        response = client.post(
            "/api/upload",
            files={"file": ("paper.pdf", f, "application/pdf")},
        )
    assert response.status_code == 200


def test_generate_rejects_non_pdf_magic_bytes(client: TestClient):
    """Generate endpoint also validates magic bytes."""
    fake_pdf = b"PK\x03\x04 this is actually a zip file"
    response = client.post(
        "/api/generate",
        headers={"X-API-Key": "sk-test"},
        files={"file": ("paper.pdf", fake_pdf, "application/pdf")},
    )
    assert response.status_code == 400
    assert "valid PDF" in response.json()["detail"]
