"""Unit tests for v3 Task 6: CI workflow configuration validation."""
from pathlib import Path

import yaml
import pytest

CI_WORKFLOW = Path(__file__).resolve().parent.parent.parent / ".github" / "workflows" / "ci.yml"


@pytest.fixture
def workflow():
    assert CI_WORKFLOW.exists(), f"CI workflow not found at {CI_WORKFLOW}"
    return yaml.safe_load(CI_WORKFLOW.read_text())


def test_workflow_triggers_on_push_and_pr(workflow):
    """CI triggers on push and pull_request."""
    # PyYAML parses 'on:' as boolean True key
    triggers = workflow.get("on") or workflow.get(True, {})
    assert "push" in triggers
    assert "pull_request" in triggers


def test_workflow_has_backend_job(workflow):
    """Workflow has a backend test job."""
    jobs = workflow["jobs"]
    assert "backend" in jobs or "test" in jobs or "backend-tests" in jobs


def test_workflow_has_e2e_job(workflow):
    """Workflow has an E2E test job."""
    jobs = workflow["jobs"]
    assert "e2e" in jobs or "e2e-tests" in jobs


def test_backend_job_runs_pytest(workflow):
    """Backend job runs pytest."""
    jobs = workflow["jobs"]
    backend = jobs.get("backend") or jobs.get("backend-tests") or jobs.get("test")
    steps_text = str(backend["steps"])
    assert "pytest" in steps_text


def test_backend_job_runs_semgrep(workflow):
    """Backend job runs semgrep."""
    jobs = workflow["jobs"]
    backend = jobs.get("backend") or jobs.get("backend-tests") or jobs.get("test")
    steps_text = str(backend["steps"])
    assert "semgrep" in steps_text


def test_backend_job_runs_pip_audit(workflow):
    """Backend job runs pip-audit."""
    jobs = workflow["jobs"]
    backend = jobs.get("backend") or jobs.get("backend-tests") or jobs.get("test")
    steps_text = str(backend["steps"])
    assert "pip-audit" in steps_text or "pip_audit" in steps_text


def test_e2e_job_runs_playwright(workflow):
    """E2E job installs and runs Playwright."""
    jobs = workflow["jobs"]
    e2e = jobs.get("e2e") or jobs.get("e2e-tests")
    steps_text = str(e2e["steps"])
    assert "playwright" in steps_text.lower()


def test_e2e_job_uploads_screenshots(workflow):
    """E2E job uploads screenshots as artifacts."""
    jobs = workflow["jobs"]
    e2e = jobs.get("e2e") or jobs.get("e2e-tests")
    steps_text = str(e2e["steps"])
    assert "upload-artifact" in steps_text or "screenshots" in steps_text


def test_uses_python_311(workflow):
    """Workflow uses Python 3.11."""
    text = str(workflow)
    assert "3.11" in text
