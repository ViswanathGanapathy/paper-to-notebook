"""Unit tests for pipeline module — error branches, sanitization, and helpers."""
import json

import pytest


def test_status_event_format():
    """_status returns correct SSE event dict."""
    from app.pipeline import _status

    event = _status("Processing paper...")
    assert event["event"] == "status"
    data = json.loads(event["data"])
    assert data["message"] == "Processing paper..."


def test_error_event_format():
    """_error returns correct SSE event dict."""
    from app.pipeline import _error

    event = _error("Something went wrong")
    assert event["event"] == "error"
    data = json.loads(event["data"])
    assert data["message"] == "Something went wrong"


def test_complete_event_has_all_fields():
    """_complete returns file_id, title, colab_url, notebook_path."""
    from app.pipeline import _complete

    event = _complete("abc-123", "Test Paper")
    assert event["event"] == "complete"
    data = json.loads(event["data"])
    assert data["file_id"] == "abc-123"
    assert data["title"] == "Test Paper"
    assert "colab_url" in data
    assert "notebook_path" in data
    assert "/api/notebook/abc-123" in data["notebook_path"]


def test_sanitize_error_connection_error():
    """Connection errors get a user-friendly message."""
    from app.pipeline import _sanitize_error

    exc = Exception("Connection refused to api.openai.com")
    result = _sanitize_error(exc)
    assert "network" in result.lower() or "connection" in result.lower()


def test_sanitize_error_never_leaks_paths():
    """No internal paths in any sanitized error."""
    from app.pipeline import _sanitize_error

    exc = Exception("/home/user/.local/lib/python3.10/site-packages/openai/error.py line 42")
    result = _sanitize_error(exc)
    assert "/home/" not in result
    assert "site-packages" not in result


def test_sanitize_filename_with_null_bytes():
    """Null bytes in filename are stripped."""
    from app.pipeline import _sanitize_filename

    result = _sanitize_filename("paper\x00.pdf")
    assert "\x00" not in result


def test_sanitize_filename_unicode():
    """Unicode filenames are handled gracefully."""
    from app.pipeline import _sanitize_filename

    result = _sanitize_filename("论文研究.pdf")
    assert len(result) > 0


def test_sanitize_filename_only_special_chars():
    """Filename with only special chars gets fallback."""
    from app.pipeline import _sanitize_filename

    result = _sanitize_filename("<<<>>>")
    assert result == "uploaded file"
