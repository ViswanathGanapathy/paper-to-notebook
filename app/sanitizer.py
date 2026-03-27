"""Prompt injection sanitizer (input) and code scanner (output).

Resolves SEC-004 (Prompt Injection) and SEC-005 (Unvalidated Code).
"""
import logging
import re
from dataclasses import dataclass

logger = logging.getLogger(__name__)

# ── Input Sanitizer ──────────────────────────────────────

# Patterns that could be used to break out of the LLM prompt delimiters
_DELIMITER_PATTERNS = [
    r"---\s*PAPER\s*TEXT\s*---",
    r"---\s*END\s*PAPER\s*---",
    r"---\s*END\s*---",
    r"---\s*PAPER\s*ANALYSIS\s*---",
    r"---\s*END\s*ANALYSIS\s*---",
    r"---\s*FULL\s*PAPER\s*TEXT[^-]*---",
]

# Common prompt injection phrases (case-insensitive)
_INJECTION_PHRASES = [
    r"ignore\s+(all\s+)?previous\s+instructions",
    r"ignore\s+(all\s+)?above\s+instructions",
    r"disregard\s+(all\s+)?previous",
    r"forget\s+(all\s+)?previous",
    r"you\s+are\s+now\s+a\s+different",
    r"new\s+instructions?\s*:",
    r"override\s+system\s+prompt",
    r"system\s*prompt\s*:",
]

# Fake system/role markers
_ROLE_MARKERS = [
    r"\[SYSTEM\]",
    r"\[ASSISTANT\]",
    r"\[USER\]",
    r"<<SYS>>",
    r"<</SYS>>",
    r"\bsystem\s*:\s*you\s+are\b",
]


def sanitize_paper_text(text: str) -> str:
    """Sanitize extracted PDF text before sending to LLM.

    Removes or neutralizes patterns that could manipulate the LLM prompt.
    Preserves legitimate academic content.
    """
    result = text

    # Strip delimiter patterns
    for pattern in _DELIMITER_PATTERNS:
        result = re.sub(pattern, "[REMOVED]", result, flags=re.IGNORECASE)

    # Strip injection phrases (remove the entire line containing them)
    for pattern in _INJECTION_PHRASES:
        result = re.sub(
            rf"^.*{pattern}.*$",
            "",
            result,
            flags=re.IGNORECASE | re.MULTILINE,
        )

    # Strip role markers
    for pattern in _ROLE_MARKERS:
        result = re.sub(pattern, "[REMOVED]", result, flags=re.IGNORECASE)

    # Clean up extra blank lines from removals
    result = re.sub(r"\n{3,}", "\n\n", result)

    return result.strip()


# ── Output Code Scanner ──────────────────────────────────

@dataclass
class ScanResult:
    """Result of scanning a code cell for dangerous patterns."""

    is_flagged: bool
    reasons: list[str]


# Dangerous patterns to detect in generated code
_DANGEROUS_PATTERNS: list[tuple[str, str]] = [
    # System command execution
    (r"\bos\.system\s*\(", "os.system() call — executes shell commands"),
    (r"\bos\.popen\s*\(", "os.popen() call — executes shell commands"),
    (r"\bsubprocess\b", "subprocess module — executes external commands"),
    (r"\b__import__\s*\(", "__import__() — dynamic module import"),

    # Code execution
    (r"\beval\s*\(", "eval() — executes arbitrary code"),
    (r"\bexec\s*\(", "exec() — executes arbitrary code"),
    (r"\bcompile\s*\(.*\bexec\b", "compile() with exec — code execution"),

    # Network exfiltration
    (r"\brequests\.post\s*\(", "requests.post() — potential data exfiltration"),
    (r"\burllib\.request\.urlopen\s*\(", "urllib — potential network access"),
    (r"!curl\b", "curl command — network access via shell"),
    (r"!wget\b", "wget command — network access via shell"),

    # Credential/sensitive file access
    (r"\.ssh/", "SSH key file access"),
    (r"\.aws/credentials", "AWS credential file access"),
    (r"\.config/gcloud", "GCloud credential file access"),
    (r"/etc/passwd", "/etc/passwd file access"),
    (r"/etc/shadow", "/etc/shadow file access"),
    (r"\.env\b", ".env file access (may contain secrets)"),
    (r"OPENAI_API_KEY", "OpenAI API key access"),
    (r"os\.environ", "os.environ access — may leak secrets"),

    # Dangerous file operations
    (r"shutil\.rmtree\s*\(", "shutil.rmtree() — recursive file deletion"),
    (r"!rm\s+-rf\b", "rm -rf — recursive file deletion"),
]

# Patterns that are safe and should NOT be flagged (allowlist)
_SAFE_EXCEPTIONS: list[str] = [
    r"^!pip\s+install",  # pip install is safe
    r"^#",               # Comments are safe
]


def scan_code_cell(code: str) -> ScanResult:
    """Scan a code cell for dangerous patterns.

    Returns a ScanResult indicating if the code was flagged and why.
    """
    reasons: list[str] = []

    for line in code.split("\n"):
        stripped = line.strip()

        # Skip safe patterns
        if any(re.match(pat, stripped) for pat in _SAFE_EXCEPTIONS):
            continue

        for pattern, description in _DANGEROUS_PATTERNS:
            if re.search(pattern, stripped, re.IGNORECASE):
                reasons.append(f"{description}: `{stripped[:80]}`")

    # Deduplicate
    unique_reasons = list(dict.fromkeys(reasons))

    return ScanResult(
        is_flagged=len(unique_reasons) > 0,
        reasons=unique_reasons,
    )


def generate_warning_cell(reasons: list[str]) -> str:
    """Generate a markdown warning for flagged code cells."""
    items = "\n".join(f"- {r}" for r in reasons[:5])
    return (
        "⚠️ **Security Warning — Review the code below before running**\n\n"
        "The following cell contains patterns that may be dangerous:\n\n"
        f"{items}\n\n"
        "*This code was AI-generated from a research paper. "
        "Please review it carefully before executing.*"
    )


# Disclaimer cell always added to generated notebooks
NOTEBOOK_DISCLAIMER = (
    "⚠️ **Disclaimer: AI-Generated Code**\n\n"
    "This notebook was automatically generated by an AI model (gpt-5.4) "
    "based on a research paper. While the code has been scanned for "
    "obviously dangerous patterns, **you should review all code cells "
    "before executing them**.\n\n"
    "The generated code may contain:\n"
    "- Errors or inaccuracies in the implementation\n"
    "- Inefficient or non-optimal approaches\n"
    "- Unexpected behaviors with different inputs\n\n"
    "*Always verify the implementation against the original paper.*"
)
