"""Unit tests for v3 Task 8: Terraform configuration validation."""
from pathlib import Path

import pytest

TF_DIR = Path(__file__).resolve().parent.parent.parent / "terraform"


def test_terraform_directory_exists():
    """terraform/ directory exists."""
    assert TF_DIR.exists() and TF_DIR.is_dir()


def test_provider_tf_exists():
    """provider.tf defines the AWS provider."""
    content = (TF_DIR / "provider.tf").read_text()
    assert "aws" in content
    assert "provider" in content


def test_variables_tf_exists():
    """variables.tf defines input variables."""
    content = (TF_DIR / "variables.tf").read_text()
    assert "variable" in content
    assert "region" in content.lower()


def test_outputs_tf_exists():
    """outputs.tf defines output values."""
    content = (TF_DIR / "outputs.tf").read_text()
    assert "output" in content


def test_main_tf_has_vpc():
    """main.tf includes VPC configuration."""
    content = (TF_DIR / "main.tf").read_text()
    assert "aws_vpc" in content


def test_main_tf_has_ecs_cluster():
    """main.tf includes ECS cluster."""
    content = (TF_DIR / "main.tf").read_text()
    assert "aws_ecs_cluster" in content


def test_main_tf_has_fargate_task():
    """main.tf includes Fargate task definition."""
    content = (TF_DIR / "main.tf").read_text()
    assert "aws_ecs_task_definition" in content
    assert "FARGATE" in content


def test_main_tf_has_ecr_repository():
    """main.tf includes ECR repository."""
    content = (TF_DIR / "main.tf").read_text()
    assert "aws_ecr_repository" in content


def test_main_tf_has_alb():
    """main.tf includes Application Load Balancer."""
    content = (TF_DIR / "main.tf").read_text()
    assert "aws_lb" in content or "aws_alb" in content


def test_main_tf_has_iam_roles():
    """main.tf includes IAM execution role."""
    content = (TF_DIR / "main.tf").read_text()
    assert "aws_iam_role" in content
    assert "ecs" in content.lower()


def test_main_tf_has_security_groups():
    """main.tf includes security groups."""
    content = (TF_DIR / "main.tf").read_text()
    assert "aws_security_group" in content


def test_main_tf_has_cloudwatch_logs():
    """main.tf includes CloudWatch log group."""
    content = (TF_DIR / "main.tf").read_text()
    assert "aws_cloudwatch_log_group" in content


def test_task_definition_memory_and_cpu():
    """Task definition defaults to 512 CPU and 1024 MiB memory."""
    variables = (TF_DIR / "variables.tf").read_text()
    assert "512" in variables   # task_cpu default
    assert "1024" in variables  # task_memory default


def test_no_hardcoded_secrets():
    """Terraform files contain no hardcoded AWS credentials."""
    for tf_file in TF_DIR.glob("*.tf"):
        content = tf_file.read_text()
        assert "AKIA" not in content, f"Hardcoded AWS key in {tf_file.name}"
        assert "secret_access_key" not in content.lower() or "var." in content
