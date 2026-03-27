"""Unit tests for Task 3: PDF text extraction with PyMuPDF."""
from pathlib import Path

import pytest

FIXTURES = Path(__file__).resolve().parent.parent / "fixtures"


@pytest.fixture
def sample_pdf() -> Path:
    return FIXTURES / "sample_paper.pdf"


@pytest.fixture
def empty_pdf() -> Path:
    return FIXTURES / "empty.pdf"


@pytest.fixture
def large_pdf() -> Path:
    return FIXTURES / "large.pdf"


def test_extract_returns_required_fields(sample_pdf: Path):
    """Extraction returns title, page_count, sections, and full_text."""
    from app.pdf_extractor import extract_pdf

    result = extract_pdf(sample_pdf.read_bytes())
    assert "title" in result
    assert "page_count" in result
    assert "sections" in result
    assert "full_text" in result


def test_extract_page_count(sample_pdf: Path):
    """Page count matches the actual PDF."""
    from app.pdf_extractor import extract_pdf

    result = extract_pdf(sample_pdf.read_bytes())
    assert result["page_count"] == 2


def test_extract_title(sample_pdf: Path):
    """Title is extracted from the first page."""
    from app.pdf_extractor import extract_pdf

    result = extract_pdf(sample_pdf.read_bytes())
    assert "Attention" in result["title"]


def test_extract_sections(sample_pdf: Path):
    """Section headers are detected and content is grouped."""
    from app.pdf_extractor import extract_pdf

    result = extract_pdf(sample_pdf.read_bytes())
    headings = [s["heading"] for s in result["sections"]]
    assert any("Abstract" in h for h in headings)
    assert any("Introduction" in h for h in headings)
    assert any("Model Architecture" in h for h in headings)


def test_extract_full_text(sample_pdf: Path):
    """Full text contains content from multiple pages."""
    from app.pdf_extractor import extract_pdf

    result = extract_pdf(sample_pdf.read_bytes())
    assert "Transformer" in result["full_text"]
    assert "encoder-decoder" in result["full_text"]


def test_empty_pdf_raises(empty_pdf: Path):
    """Empty/scanned PDF raises an error."""
    from app.pdf_extractor import extract_pdf, PDFExtractionError

    with pytest.raises(PDFExtractionError, match="[Nn]o.*text"):
        extract_pdf(empty_pdf.read_bytes())


def test_large_pdf_raises(large_pdf: Path):
    """PDF exceeding page limit raises an error."""
    from app.pdf_extractor import extract_pdf, PDFExtractionError

    with pytest.raises(PDFExtractionError, match="50"):
        extract_pdf(large_pdf.read_bytes())


def test_invalid_bytes_raises():
    """Non-PDF bytes raise an error."""
    from app.pdf_extractor import extract_pdf, PDFExtractionError

    with pytest.raises(PDFExtractionError):
        extract_pdf(b"not a pdf file")
