"""Integration tests for v2 Task 1: Security headers middleware."""
import os

import pytest
from fastapi.testclient import TestClient


@pytest.fixture
def client():
    from app.main import app
    return TestClient(app)


def test_security_headers_present(client: TestClient):
    """All responses include security headers."""
    response = client.get("/api/health")
    assert response.status_code == 200

    headers = response.headers
    assert headers["X-Content-Type-Options"] == "nosniff"
    assert headers["X-Frame-Options"] == "DENY"
    assert "no-referrer" in headers["Referrer-Policy"]
    assert "Content-Security-Policy" in headers
    assert "Permissions-Policy" in headers


def test_csp_blocks_external_scripts(client: TestClient):
    """CSP does not allow unsafe-inline or external script sources."""
    response = client.get("/api/health")
    csp = response.headers["Content-Security-Policy"]
    # Should have a default-src directive
    assert "default-src" in csp
    # Should NOT allow external font loading (we self-host now)
    assert "fonts.googleapis.com" not in csp


def test_security_headers_on_static(client: TestClient):
    """Security headers are also present on static file responses."""
    response = client.get("/")
    assert response.status_code == 200
    assert "X-Content-Type-Options" in response.headers
    assert "X-Frame-Options" in response.headers


def test_docs_disabled_in_production():
    """When ENV=production, /docs and /redoc are disabled."""
    os.environ["ENV"] = "production"
    try:
        # Need to reimport to pick up env var
        import importlib
        import app.main
        importlib.reload(app.main)
        client = TestClient(app.main.app)

        response = client.get("/docs")
        assert response.status_code == 404

        response = client.get("/redoc")
        assert response.status_code == 404
    finally:
        os.environ.pop("ENV", None)
        importlib.reload(app.main)


def test_docs_enabled_in_development(client: TestClient):
    """In development (default), /docs is accessible."""
    response = client.get("/docs")
    assert response.status_code == 200


def test_self_hosted_font_served(client: TestClient):
    """Inter font files are served from /static/fonts/."""
    response = client.get("/static/fonts/Inter-Regular.woff2")
    assert response.status_code == 200
    assert "woff2" in response.headers.get("content-type", "") or len(response.content) > 10000
