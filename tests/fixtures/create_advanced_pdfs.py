"""Create advanced test PDF fixtures for multi-column, tables, and math."""
import fitz
from pathlib import Path

FIXTURES_DIR = Path(__file__).parent


def create_two_column_pdf(path: Path) -> None:
    """Create a PDF with a two-column layout (like ACM/IEEE papers)."""
    doc = fitz.open()
    page = doc.new_page(width=612, height=792)

    # Title (full width, large font)
    page.insert_text((72, 60), "Two-Column Paper Title", fontsize=18, fontname="helv")

    # Authors
    page.insert_text((72, 85), "Author A, Author B", fontsize=10, fontname="helv")

    # Section heading (full width)
    page.insert_text((72, 120), "1 Introduction", fontsize=14, fontname="helv")

    # Left column content (x: 72-290)
    page.insert_text(
        (72, 145),
        "This is the left column of a two-column\n"
        "layout paper. It contains the first part\n"
        "of the introduction section discussing\n"
        "the motivation for this work.",
        fontsize=10, fontname="helv",
    )

    # Right column content (x: 320-540)
    page.insert_text(
        (320, 145),
        "This is the right column continuing\n"
        "the introduction. It discusses related\n"
        "work and the main contributions of\n"
        "this research paper.",
        fontsize=10, fontname="helv",
    )

    # Section 2 heading
    page.insert_text((72, 260), "2 Methodology", fontsize=14, fontname="helv")

    # Left column
    page.insert_text(
        (72, 285),
        "The methodology section describes\n"
        "the proposed algorithm in detail.",
        fontsize=10, fontname="helv",
    )

    # Right column
    page.insert_text(
        (320, 285),
        "We evaluate our method on standard\n"
        "benchmarks and report results.",
        fontsize=10, fontname="helv",
    )

    doc.save(str(path))
    doc.close()


def create_table_pdf(path: Path) -> None:
    """Create a PDF with a table-like structure."""
    doc = fitz.open()
    page = doc.new_page(width=612, height=792)

    page.insert_text((72, 60), "Paper with Table", fontsize=18, fontname="helv")
    page.insert_text((72, 100), "1 Results", fontsize=14, fontname="helv")
    page.insert_text((72, 125), "Table 1 shows our results:", fontsize=10, fontname="helv")

    # Simulate table with aligned text
    y = 150
    page.insert_text((72, y), "Model          Accuracy    F1-Score", fontsize=10, fontname="helv")
    page.insert_text((72, y + 15), "Baseline       0.78        0.75", fontsize=10, fontname="helv")
    page.insert_text((72, y + 30), "Ours           0.92        0.89", fontsize=10, fontname="helv")
    page.insert_text((72, y + 45), "Ours+Ensemble  0.95        0.93", fontsize=10, fontname="helv")

    doc.save(str(path))
    doc.close()


def create_numbered_sections_pdf(path: Path) -> None:
    """Create a PDF with numbered section headings (same font size as body)."""
    doc = fitz.open()
    page = doc.new_page(width=612, height=792)

    # Title is larger
    page.insert_text((72, 60), "Paper With Numbered Sections", fontsize=18, fontname="helv")

    # All sections use same font size as body (10pt) — must detect by numbering pattern
    page.insert_text((72, 100), "1. Introduction", fontsize=10, fontname="helv")
    page.insert_text((72, 120), "This paper introduces a new method.", fontsize=10, fontname="helv")

    page.insert_text((72, 160), "2. Background", fontsize=10, fontname="helv")
    page.insert_text((72, 180), "Prior work has explored several approaches.", fontsize=10, fontname="helv")

    page.insert_text((72, 220), "3.1 Sub-section Example", fontsize=10, fontname="helv")
    page.insert_text((72, 240), "This is a subsection with details.", fontsize=10, fontname="helv")

    page.insert_text((72, 280), "4 Experiments", fontsize=10, fontname="helv")
    page.insert_text((72, 300), "We evaluate on three benchmarks.", fontsize=10, fontname="helv")

    doc.save(str(path))
    doc.close()


if __name__ == "__main__":
    create_two_column_pdf(FIXTURES_DIR / "two_column.pdf")
    create_table_pdf(FIXTURES_DIR / "table_paper.pdf")
    create_numbered_sections_pdf(FIXTURES_DIR / "numbered_sections.pdf")
    print("Advanced test fixtures created.")
