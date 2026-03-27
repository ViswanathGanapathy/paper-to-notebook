"""Unit tests for v2 Task 4: Magic byte validation and size pre-check."""
import pytest


def test_validate_magic_bytes_valid_pdf():
    """Valid PDF magic bytes pass validation."""
    from app.errors import validate_pdf_magic_bytes

    # %PDF- is the magic byte sequence
    validate_pdf_magic_bytes(b"%PDF-1.7 rest of file...")


def test_validate_magic_bytes_rejects_non_pdf():
    """Non-PDF bytes are rejected."""
    from app.errors import validate_pdf_magic_bytes, UploadValidationError

    with pytest.raises(UploadValidationError, match="[Nn]ot.*valid.*PDF"):
        validate_pdf_magic_bytes(b"PK\x03\x04 this is a zip")


def test_validate_magic_bytes_rejects_empty():
    """Empty bytes are rejected."""
    from app.errors import validate_pdf_magic_bytes, UploadValidationError

    with pytest.raises(UploadValidationError):
        validate_pdf_magic_bytes(b"")


def test_validate_magic_bytes_rejects_short():
    """Too-short bytes are rejected."""
    from app.errors import validate_pdf_magic_bytes, UploadValidationError

    with pytest.raises(UploadValidationError):
        validate_pdf_magic_bytes(b"%PD")


def test_validate_magic_bytes_rejects_html_disguised_as_pdf():
    """HTML file renamed to .pdf is rejected."""
    from app.errors import validate_pdf_magic_bytes, UploadValidationError

    with pytest.raises(UploadValidationError):
        validate_pdf_magic_bytes(b"<!DOCTYPE html><html>...")


def test_content_length_check_rejects_oversized():
    """Content-Length over limit is caught."""
    from app.errors import validate_content_length, UploadValidationError, MAX_FILE_SIZE_MB

    huge = (MAX_FILE_SIZE_MB + 1) * 1024 * 1024
    with pytest.raises(UploadValidationError, match="[Ss]ize"):
        validate_content_length(huge)


def test_content_length_check_accepts_valid():
    """Normal Content-Length passes."""
    from app.errors import validate_content_length

    validate_content_length(1024 * 1024)  # 1 MB


def test_content_length_check_accepts_zero():
    """Zero or None content-length is allowed (will be caught later)."""
    from app.errors import validate_content_length

    validate_content_length(0)
    validate_content_length(None)
