"""Unit tests for v3 Task 7: Docker configuration validation."""
from pathlib import Path

import yaml
import pytest

PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent


@pytest.fixture
def dockerfile():
    path = PROJECT_ROOT / "Dockerfile"
    assert path.exists(), "Dockerfile not found"
    return path.read_text()


@pytest.fixture
def compose():
    path = PROJECT_ROOT / "docker-compose.yml"
    assert path.exists(), "docker-compose.yml not found"
    return yaml.safe_load(path.read_text())


@pytest.fixture
def dockerignore():
    path = PROJECT_ROOT / ".dockerignore"
    assert path.exists(), ".dockerignore not found"
    return path.read_text()


def test_dockerfile_uses_python_311_slim(dockerfile):
    """Dockerfile uses python:3.11-slim base image."""
    assert "python:3.11-slim" in dockerfile


def test_dockerfile_copies_requirements_first(dockerfile):
    """Dockerfile copies requirements.txt before app code (layer caching)."""
    req_pos = dockerfile.find("requirements.txt")
    app_pos = dockerfile.find("COPY app/")
    if app_pos == -1:
        app_pos = dockerfile.find("COPY . .")
    assert req_pos < app_pos, "requirements.txt should be copied before app code"


def test_dockerfile_runs_uvicorn(dockerfile):
    """Dockerfile CMD/ENTRYPOINT runs uvicorn."""
    assert "uvicorn" in dockerfile


def test_dockerfile_exposes_port_8000(dockerfile):
    """Dockerfile exposes port 8000."""
    assert "8000" in dockerfile


def test_dockerfile_does_not_run_as_root(dockerfile):
    """Dockerfile creates a non-root user."""
    assert "USER" in dockerfile or "useradd" in dockerfile or "adduser" in dockerfile


def test_compose_has_app_service(compose):
    """docker-compose defines the app service."""
    services = compose.get("services", {})
    assert len(services) >= 1
    service_name = list(services.keys())[0]
    assert "app" in service_name or "p2n" in service_name


def test_compose_maps_port_8000(compose):
    """docker-compose maps port 8000."""
    services = compose.get("services", {})
    service = list(services.values())[0]
    ports = str(service.get("ports", []))
    assert "8000" in ports


def test_compose_sets_production_env(compose):
    """docker-compose sets ENV=production."""
    services = compose.get("services", {})
    service = list(services.values())[0]
    env = str(service.get("environment", {}))
    assert "production" in env.lower()


def test_compose_mounts_generated_volume(compose):
    """docker-compose mounts generated/ as a volume."""
    services = compose.get("services", {})
    service = list(services.values())[0]
    volumes = str(service.get("volumes", []))
    assert "generated" in volumes


def test_dockerignore_excludes_venv(dockerignore):
    """Docker ignore excludes venv and other dev artifacts."""
    assert "venv" in dockerignore
    assert ".git" in dockerignore


def test_dockerignore_excludes_secrets(dockerignore):
    """Docker ignore excludes secret files."""
    assert ".env" in dockerignore
    assert "accessKeys" in dockerignore or "*.csv" in dockerignore
