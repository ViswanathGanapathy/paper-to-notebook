"""Unit tests for v3 Task 10: README and final validation."""
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent


def test_readme_exists():
    """README.md exists in the project root."""
    assert (PROJECT_ROOT / "README.md").exists()


def test_readme_has_required_sections():
    """README contains all required sections."""
    content = (PROJECT_ROOT / "README.md").read_text()
    required = [
        "Paper-to-Notebook",
        "Quick Start",
        "Docker",
        "Testing",
        "CI/CD",
        "AWS",
        "Security",
    ]
    for section in required:
        assert section.lower() in content.lower(), f"README missing section: {section}"


def test_readme_no_secrets():
    """README does not contain actual secret values (placeholder names are OK)."""
    content = (PROJECT_ROOT / "README.md").read_text()
    assert "AKIA" not in content  # No real AWS access key IDs
    # Placeholder references like AWS_SECRET_ACCESS_KEY (the secret name) are OK
    # but actual secret values (long random strings) are not
    import re
    assert not re.search(r"sk-[a-zA-Z0-9]{20,}", content), "Actual OpenAI key found"
    assert not re.search(r"AKIA[A-Z0-9]{16}", content), "Actual AWS key found"


def test_total_test_count():
    """Project has 200+ tests total."""
    import subprocess
    result = subprocess.run(
        ["python", "-m", "pytest", "tests/", "--ignore=tests/fixtures",
         "--ignore=tests/quality", "--collect-only", "-q"],
        capture_output=True, text=True, cwd=str(PROJECT_ROOT),
    )
    # Parse "N tests collected"
    last_line = result.stdout.strip().split("\n")[-1]
    count = int(last_line.split()[0])
    assert count >= 200, f"Expected 200+ tests, got {count}"


def test_test_pyramid_ratios():
    """Test pyramid: unit tests outnumber integration tests."""
    import subprocess

    def count_tests(path):
        r = subprocess.run(
            ["python", "-m", "pytest", path, "--collect-only", "-q"],
            capture_output=True, text=True, cwd=str(PROJECT_ROOT),
        )
        last_line = r.stdout.strip().split("\n")[-1]
        try:
            return int(last_line.split()[0])
        except (ValueError, IndexError):
            return 0  # Playwright not installed → 0 E2E tests

    unit = count_tests("tests/unit/")
    integration = count_tests("tests/integration/")

    assert unit >= 100, f"Expected 100+ unit tests, got {unit}"
    assert integration >= 30, f"Expected 30+ integration tests, got {integration}"
    assert unit > integration, "Unit tests should outnumber integration tests"
