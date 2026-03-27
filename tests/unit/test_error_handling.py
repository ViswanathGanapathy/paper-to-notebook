"""Unit tests for Task 9: Error handling and validation."""
from pathlib import Path

import pytest


def test_sanitize_error_auth():
    """Auth errors produce user-friendly message."""
    from app.pipeline import _sanitize_error

    exc = Exception("Error code: 401 - authentication failed for api_key")
    result = _sanitize_error(exc)
    assert "API key" in result
    assert "401" not in result  # No raw error codes


def test_sanitize_error_rate_limit():
    """Rate limit errors produce user-friendly message."""
    from app.pipeline import _sanitize_error

    exc = Exception("Rate limit exceeded. Please retry after 20s")
    result = _sanitize_error(exc)
    assert "rate limit" in result.lower()


def test_sanitize_error_timeout():
    """Timeout errors produce user-friendly message."""
    from app.pipeline import _sanitize_error

    exc = Exception("Request timeout after 60s")
    result = _sanitize_error(exc)
    assert "timed out" in result.lower()


def test_sanitize_error_generic():
    """Unknown errors still produce a message."""
    from app.pipeline import _sanitize_error

    exc = Exception("Something went wrong")
    result = _sanitize_error(exc)
    assert len(result) > 0


def test_pdf_extraction_error_is_exception():
    """PDFExtractionError is an Exception subclass."""
    from app.pdf_extractor import PDFExtractionError

    with pytest.raises(PDFExtractionError):
        raise PDFExtractionError("test error")


def test_max_file_size_constant_exists():
    """MAX_FILE_SIZE_MB is defined for validation."""
    from app.errors import MAX_FILE_SIZE_MB

    assert isinstance(MAX_FILE_SIZE_MB, (int, float))
    assert MAX_FILE_SIZE_MB > 0


def test_validate_pdf_upload_rejects_non_pdf():
    """validate_pdf_upload rejects non-PDF filenames."""
    from app.errors import validate_pdf_upload, UploadValidationError

    with pytest.raises(UploadValidationError, match="PDF"):
        validate_pdf_upload("readme.txt", 1000)


def test_validate_pdf_upload_rejects_oversized():
    """validate_pdf_upload rejects files over size limit."""
    from app.errors import validate_pdf_upload, UploadValidationError, MAX_FILE_SIZE_MB

    huge_size = (MAX_FILE_SIZE_MB + 1) * 1024 * 1024
    with pytest.raises(UploadValidationError, match="[Ss]ize"):
        validate_pdf_upload("paper.pdf", int(huge_size))


def test_validate_pdf_upload_accepts_valid():
    """validate_pdf_upload accepts a valid PDF filename and size."""
    from app.errors import validate_pdf_upload

    # Should not raise
    validate_pdf_upload("paper.pdf", 1024 * 1024)


def test_validate_pdf_upload_rejects_empty_filename():
    """validate_pdf_upload rejects empty filename."""
    from app.errors import validate_pdf_upload, UploadValidationError

    with pytest.raises(UploadValidationError):
        validate_pdf_upload("", 1000)
