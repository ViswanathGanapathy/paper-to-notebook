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
    """Test pyramid is approximately 70/20/10."""
    import subprocess

    def count_tests(path):
        r = subprocess.run(
            ["python", "-m", "pytest", path, "--collect-only", "-q"],
            capture_output=True, text=True, cwd=str(PROJECT_ROOT),
        )
        return int(r.stdout.strip().split("\n")[-1].split()[0])

    unit = count_tests("tests/unit/")
    integration = count_tests("tests/integration/")
    e2e = count_tests("tests/e2e/")
    total = unit + integration + e2e

    unit_pct = unit / total * 100
    integration_pct = integration / total * 100
    e2e_pct = e2e / total * 100

    assert unit_pct >= 50, f"Unit tests should be >= 50% (got {unit_pct:.0f}%)"
    assert integration_pct >= 15, f"Integration tests should be >= 15% (got {integration_pct:.0f}%)"
    assert e2e_pct >= 5, f"E2E tests should be >= 5% (got {e2e_pct:.0f}%)"
