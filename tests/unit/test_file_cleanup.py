"""Unit tests for v2 Task 6: File cleanup + error sanitization."""
import time
from pathlib import Path

import pytest


def test_cleanup_removes_old_files(tmp_path: Path):
    """cleanup_generated_files removes files older than max_age_seconds."""
    from app.cleanup import cleanup_generated_files

    # Create an "old" file with a modified time in the past
    old_file = tmp_path / "old-notebook.ipynb"
    old_file.write_text("{}")
    # Set mtime to 2 hours ago
    import os
    old_mtime = time.time() - 7200
    os.utime(old_file, (old_mtime, old_mtime))

    # Create a "new" file
    new_file = tmp_path / "new-notebook.ipynb"
    new_file.write_text("{}")

    removed = cleanup_generated_files(tmp_path, max_age_seconds=3600)

    assert not old_file.exists(), "Old file should be deleted"
    assert new_file.exists(), "New file should be preserved"
    assert removed == 1


def test_cleanup_ignores_non_ipynb(tmp_path: Path):
    """Cleanup only deletes .ipynb files."""
    from app.cleanup import cleanup_generated_files

    other_file = tmp_path / "readme.txt"
    other_file.write_text("keep me")
    import os
    old_mtime = time.time() - 7200
    os.utime(other_file, (old_mtime, old_mtime))

    removed = cleanup_generated_files(tmp_path, max_age_seconds=3600)

    assert other_file.exists()
    assert removed == 0


def test_cleanup_handles_empty_dir(tmp_path: Path):
    """Cleanup works on empty directory."""
    from app.cleanup import cleanup_generated_files

    removed = cleanup_generated_files(tmp_path, max_age_seconds=3600)
    assert removed == 0


def test_sanitize_error_generic_fallback():
    """Unrecognized errors return a generic message, not raw exception text."""
    from app.pipeline import _sanitize_error

    exc = Exception("Internal: /home/user/.venv/lib/python3.10/traceback details here")
    result = _sanitize_error(exc)
    assert "/home/user" not in result
    assert ".venv" not in result
    assert "traceback" not in result.lower()


def test_sanitize_error_no_raw_exception_for_unknown():
    """Unknown errors don't leak the raw exception message."""
    from app.pipeline import _sanitize_error

    exc = Exception("psycopg2.OperationalError: connection refused at 10.0.0.1:5432")
    result = _sanitize_error(exc)
    assert "10.0.0.1" not in result
    assert "psycopg2" not in result


def test_sanitize_filename_strips_html():
    """Filenames with HTML are sanitized before reflection."""
    from app.pipeline import _sanitize_filename

    name = '<img src=x onerror=alert(1)>.pdf'
    result = _sanitize_filename(name)
    assert "<" not in result
    assert ">" not in result
    assert "onerror" not in result


def test_sanitize_filename_truncates_long_names():
    """Very long filenames are truncated."""
    from app.pipeline import _sanitize_filename

    name = "a" * 300 + ".pdf"
    result = _sanitize_filename(name)
    assert len(result) <= 100


def test_sanitize_filename_preserves_normal_names():
    """Normal PDF filenames are preserved."""
    from app.pipeline import _sanitize_filename

    assert _sanitize_filename("attention_is_all_you_need.pdf") == "attention_is_all_you_need.pdf"
