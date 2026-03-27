"""Create test PDF fixtures for testing PDF extraction."""
import fitz  # PyMuPDF
from pathlib import Path

FIXTURES_DIR = Path(__file__).parent


def create_research_paper_pdf(path: Path) -> None:
    """Create a realistic multi-section research paper PDF."""
    doc = fitz.open()

    # Page 1: Title, authors, abstract
    page = doc.new_page(width=612, height=792)
    # Title (large font)
    page.insert_text(
        (72, 80), "Attention Is All You Need",
        fontsize=20, fontname="helv",
    )
    # Authors
    page.insert_text(
        (72, 110), "Ashish Vaswani, Noam Shazeer, Niki Parmar",
        fontsize=11, fontname="helv",
    )
    # Abstract heading
    page.insert_text(
        (72, 150), "Abstract",
        fontsize=14, fontname="helv",
    )
    page.insert_text(
        (72, 170),
        "The dominant sequence transduction models are based on complex recurrent or\n"
        "convolutional neural networks that include an encoder and a decoder. The best\n"
        "performing models also connect the encoder and decoder through an attention mechanism.\n"
        "We propose a new simple network architecture, the Transformer, based solely on\n"
        "attention mechanisms, dispensing with recurrence and convolutions entirely.",
        fontsize=10, fontname="helv",
    )

    # Section 1
    page.insert_text(
        (72, 280), "1 Introduction",
        fontsize=14, fontname="helv",
    )
    page.insert_text(
        (72, 300),
        "Recurrent neural networks, long short-term memory and gated recurrent neural\n"
        "networks in particular, have been firmly established as state of the art approaches\n"
        "in sequence modeling and transduction problems such as language modeling and\n"
        "machine translation.",
        fontsize=10, fontname="helv",
    )

    # Page 2: More sections
    page2 = doc.new_page(width=612, height=792)
    page2.insert_text(
        (72, 80), "2 Background",
        fontsize=14, fontname="helv",
    )
    page2.insert_text(
        (72, 100),
        "The goal of reducing sequential computation also forms the foundation of the\n"
        "Extended Neural GPU, ByteNet and ConvS2S, all of which use convolutional neural\n"
        "networks as basic building block.",
        fontsize=10, fontname="helv",
    )

    page2.insert_text(
        (72, 180), "3 Model Architecture",
        fontsize=14, fontname="helv",
    )
    page2.insert_text(
        (72, 200),
        "Most competitive neural sequence transduction models have an encoder-decoder\n"
        "structure. Here, the encoder maps an input sequence of symbol representations\n"
        "to a sequence of continuous representations.",
        fontsize=10, fontname="helv",
    )

    doc.save(str(path))
    doc.close()


def create_empty_pdf(path: Path) -> None:
    """Create an empty PDF with no text (simulates scanned PDF)."""
    doc = fitz.open()
    doc.new_page(width=612, height=792)
    doc.save(str(path))
    doc.close()


def create_large_pdf(path: Path, pages: int = 55) -> None:
    """Create a PDF with many pages to test the page limit."""
    doc = fitz.open()
    for i in range(pages):
        page = doc.new_page(width=612, height=792)
        page.insert_text((72, 80), f"Page {i + 1} content", fontsize=10, fontname="helv")
    doc.save(str(path))
    doc.close()


if __name__ == "__main__":
    create_research_paper_pdf(FIXTURES_DIR / "sample_paper.pdf")
    create_empty_pdf(FIXTURES_DIR / "empty.pdf")
    create_large_pdf(FIXTURES_DIR / "large.pdf")
    print("Test fixtures created.")
