"""Unit tests for v2 Task 7: Enhanced PDF extraction."""
from pathlib import Path

import pytest

FIXTURES = Path(__file__).resolve().parent.parent / "fixtures"


@pytest.fixture
def two_column_pdf() -> Path:
    return FIXTURES / "two_column.pdf"


@pytest.fixture
def table_pdf() -> Path:
    return FIXTURES / "table_paper.pdf"


@pytest.fixture
def numbered_sections_pdf() -> Path:
    return FIXTURES / "numbered_sections.pdf"


def test_two_column_extracts_both_columns(two_column_pdf: Path):
    """Two-column PDF extracts text from both columns."""
    from app.pdf_extractor import extract_pdf

    result = extract_pdf(two_column_pdf.read_bytes())
    full_text = result["full_text"]

    assert "left column" in full_text.lower()
    assert "right column" in full_text.lower()


def test_two_column_reading_order(two_column_pdf: Path):
    """Two-column PDF text is in reading order (left col before right col)."""
    from app.pdf_extractor import extract_pdf

    result = extract_pdf(two_column_pdf.read_bytes())
    full_text = result["full_text"]

    left_pos = full_text.lower().find("left column")
    right_pos = full_text.lower().find("right column")
    assert left_pos < right_pos, "Left column text should appear before right column"


def test_two_column_sections_detected(two_column_pdf: Path):
    """Sections are detected in two-column papers."""
    from app.pdf_extractor import extract_pdf

    result = extract_pdf(two_column_pdf.read_bytes())
    headings = [s["heading"] for s in result["sections"]]
    assert any("Introduction" in h for h in headings)
    assert any("Methodology" in h for h in headings)


def test_table_content_extracted(table_pdf: Path):
    """Table content is present in extracted text."""
    from app.pdf_extractor import extract_pdf

    result = extract_pdf(table_pdf.read_bytes())
    full_text = result["full_text"]

    assert "Baseline" in full_text
    assert "0.92" in full_text
    assert "Accuracy" in full_text


def test_numbered_sections_detected_by_pattern(numbered_sections_pdf: Path):
    """Numbered headings (same font size) are detected by numbering pattern."""
    from app.pdf_extractor import extract_pdf

    result = extract_pdf(numbered_sections_pdf.read_bytes())
    headings = [s["heading"] for s in result["sections"]]

    # Should detect at least some numbered sections
    assert any("Introduction" in h for h in headings)
    assert any("Background" in h for h in headings)


def test_numbered_subsections_detected(numbered_sections_pdf: Path):
    """Subsection headings like '3.1 ...' are also detected."""
    from app.pdf_extractor import extract_pdf

    result = extract_pdf(numbered_sections_pdf.read_bytes())
    headings = [s["heading"] for s in result["sections"]]

    assert any("Sub-section" in h or "3.1" in h for h in headings)
