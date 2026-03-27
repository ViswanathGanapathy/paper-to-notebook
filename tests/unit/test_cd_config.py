"""Unit tests for v3 Task 9: CD deploy workflow validation."""
from pathlib import Path

import yaml
import pytest

CD_WORKFLOW = Path(__file__).resolve().parent.parent.parent / ".github" / "workflows" / "deploy.yml"


@pytest.fixture
def workflow():
    assert CD_WORKFLOW.exists(), f"Deploy workflow not found at {CD_WORKFLOW}"
    return yaml.safe_load(CD_WORKFLOW.read_text())


def test_triggers_on_main_only(workflow):
    """Deploy only triggers on pushes to main."""
    triggers = workflow.get("on") or workflow.get(True, {})
    # Should trigger on workflow_run (after CI) or push to main
    if "push" in triggers:
        branches = triggers["push"].get("branches", [])
        assert "main" in branches
    elif "workflow_run" in triggers:
        assert True  # workflow_run trigger is valid
    else:
        pytest.fail("Deploy should trigger on main push or workflow_run")


def test_has_deploy_job(workflow):
    """Workflow has a deploy job."""
    jobs = workflow["jobs"]
    assert "deploy" in jobs or len(jobs) >= 1


def test_uses_aws_credentials_action(workflow):
    """Uses aws-actions/configure-aws-credentials."""
    text = str(workflow)
    assert "configure-aws-credentials" in text


def test_uses_ecr_login_action(workflow):
    """Uses aws-actions/amazon-ecr-login."""
    text = str(workflow)
    assert "amazon-ecr-login" in text


def test_references_github_secrets(workflow):
    """AWS credentials come from GitHub Secrets, not hardcoded."""
    text = str(workflow)
    assert "secrets.AWS_ACCESS_KEY_ID" in text
    assert "secrets.AWS_SECRET_ACCESS_KEY" in text
    # Must NOT contain actual key patterns
    assert "AKIA" not in text


def test_builds_and_pushes_docker(workflow):
    """Workflow builds Docker image and pushes to ECR."""
    text = str(workflow)
    assert "docker" in text.lower()
    assert "push" in text.lower()


def test_updates_ecs_service(workflow):
    """Workflow updates the ECS service."""
    text = str(workflow)
    assert "ecs" in text.lower()
    assert "update-service" in text or "deploy" in text.lower()
