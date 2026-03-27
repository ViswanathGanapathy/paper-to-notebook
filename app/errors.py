"""Custom exceptions and validation for Paper-to-Notebook."""
from __future__ import annotations

MAX_FILE_SIZE_MB = 50  # Maximum PDF file size in megabytes
PDF_MAGIC_BYTES = b"%PDF-"


class UploadValidationError(Exception):
    """Raised when an uploaded file fails validation."""


def validate_pdf_upload(filename: str, file_size: int) -> None:
    """Validate a PDF upload — filename and size.

    Raises UploadValidationError with a user-friendly message on failure.
    """
    if not filename:
        raise UploadValidationError("No file provided. Please upload a PDF file.")

    if not filename.lower().endswith(".pdf"):
        raise UploadValidationError(
            "Only PDF files are accepted. "
            f"You uploaded '{filename}' — please select a .pdf file."
        )

    max_bytes = MAX_FILE_SIZE_MB * 1024 * 1024
    if file_size > max_bytes:
        size_mb = file_size / (1024 * 1024)
        raise UploadValidationError(
            f"File size ({size_mb:.1f} MB) exceeds the {MAX_FILE_SIZE_MB} MB limit. "
            "Please upload a smaller PDF."
        )


def validate_pdf_magic_bytes(data: bytes) -> None:
    """Validate that data starts with PDF magic bytes (%PDF-).

    Raises UploadValidationError if the file is not a valid PDF.
    """
    if len(data) < len(PDF_MAGIC_BYTES):
        raise UploadValidationError(
            "File is too small to be a valid PDF. Please upload a proper PDF file."
        )
    if not data[:len(PDF_MAGIC_BYTES)] == PDF_MAGIC_BYTES:
        raise UploadValidationError(
            "File does not appear to be a valid PDF (missing PDF header). "
            "Please upload a genuine .pdf file."
        )


def validate_content_length(content_length: int | None) -> None:
    """Pre-check Content-Length header before reading body.

    Raises UploadValidationError if declared size exceeds limit.
    Allows 0/None (will be caught by later validation).
    """
    if content_length is None or content_length <= 0:
        return  # Unknown size — will be validated after read

    max_bytes = MAX_FILE_SIZE_MB * 1024 * 1024
    if content_length > max_bytes:
        size_mb = content_length / (1024 * 1024)
        raise UploadValidationError(
            f"File size ({size_mb:.1f} MB) exceeds the {MAX_FILE_SIZE_MB} MB limit. "
            "Please upload a smaller PDF."
        )
