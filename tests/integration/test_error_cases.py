"""Integration tests for Task 9: Error handling edge cases at API level."""
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

FIXTURES = Path(__file__).resolve().parent.parent / "fixtures"


@pytest.fixture
def client():
    from app.main import app
    return TestClient(app)


def test_upload_oversized_file(client: TestClient):
    """Uploading a file that exceeds the size limit returns 400."""
    # Create a large-ish fake PDF (just needs to exceed limit in validation)
    # We'll test with the actual large.pdf fixture which has 55 pages
    pdf_path = FIXTURES / "large.pdf"
    with open(pdf_path, "rb") as f:
        response = client.post(
            "/api/upload",
            files={"file": ("large.pdf", f, "application/pdf")},
        )
    assert response.status_code == 400


def test_generate_non_pdf_returns_400(client: TestClient):
    """Sending a non-PDF to /api/generate returns 400."""
    response = client.post(
        "/api/generate",
        headers={"X-API-Key": "sk-test"},
        files={"file": ("test.txt", b"not a pdf", "text/plain")},
    )
    assert response.status_code == 400
    assert "PDF" in response.json()["detail"]


def test_generate_empty_filename_returns_400(client: TestClient):
    """Sending a file with no .pdf extension returns 400."""
    response = client.post(
        "/api/generate",
        headers={"X-API-Key": "sk-test"},
        files={"file": ("noextension", b"data", "application/octet-stream")},
    )
    assert response.status_code == 400


def test_download_path_traversal_blocked(client: TestClient):
    """Path traversal attempts in download return 404."""
    response = client.get("/api/download/../../etc/passwd")
    assert response.status_code == 404

    response = client.get("/api/download/..%2F..%2Fetc%2Fpasswd")
    assert response.status_code == 404


def test_notebook_path_traversal_blocked(client: TestClient):
    """Path traversal attempts in notebook endpoint return 404."""
    response = client.get("/api/notebook/../../etc/passwd")
    assert response.status_code == 404
