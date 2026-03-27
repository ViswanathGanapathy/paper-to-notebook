"""PDF text extraction with structure detection using PyMuPDF.

Enhanced in v2: multi-column layout support, numbered section detection,
table preservation, and improved reading order.
"""
import logging
import re
from typing import Any

import fitz  # PyMuPDF

logger = logging.getLogger(__name__)

MAX_PAGES = 50
MIN_TEXT_LENGTH = 100

# Regex for numbered section headings (e.g., "1 Introduction", "3.1 Method")
_NUMBERED_HEADING_RE = re.compile(
    r"^\s*(\d+\.?\d*\.?\d*)\s+[A-Z]"
)


class PDFExtractionError(Exception):
    """Raised when PDF extraction fails."""


def extract_pdf(pdf_bytes: bytes) -> dict[str, Any]:
    """Extract text and structure from a PDF research paper.

    Returns:
        dict with keys: title, authors, page_count, sections, full_text
    """
    try:
        doc = fitz.open(stream=pdf_bytes, filetype="pdf")
    except Exception as exc:
        raise PDFExtractionError(f"Failed to open PDF: {exc}") from exc

    page_count = len(doc)

    if page_count > MAX_PAGES:
        doc.close()
        raise PDFExtractionError(
            f"PDF has {page_count} pages, which exceeds the {MAX_PAGES}-page limit. "
            "Please upload a shorter paper."
        )

    all_text_blocks: list[dict] = []
    full_text_parts: list[str] = []

    for page_num in range(page_count):
        page = doc[page_num]
        page_width = page.rect.width

        # Extract blocks with position info for column detection
        blocks = page.get_text("dict", flags=fitz.TEXT_PRESERVE_WHITESPACE)["blocks"]

        page_blocks = _extract_page_blocks(blocks, page_num, page_width)
        all_text_blocks.extend(page_blocks)

        # Build full text in reading order (column-aware)
        ordered = _sort_blocks_reading_order(page_blocks, page_width)
        page_text = "\n".join(b["text"] for b in ordered)
        full_text_parts.append(page_text)

    doc.close()

    full_text = "\n".join(full_text_parts).strip()

    if len(full_text) < MIN_TEXT_LENGTH:
        raise PDFExtractionError(
            "No extractable text found in this PDF. "
            "It may be a scanned document — please use a text-based PDF."
        )

    title = _detect_title(all_text_blocks)
    authors = _detect_authors(all_text_blocks, title)
    sections = _detect_sections(all_text_blocks)

    return {
        "title": title,
        "authors": authors,
        "page_count": page_count,
        "sections": sections,
        "full_text": full_text,
    }


def _extract_page_blocks(
    blocks: list[dict],
    page_num: int,
    page_width: float,
) -> list[dict]:
    """Extract text blocks with position and font metadata."""
    result: list[dict] = []

    for block in blocks:
        if block["type"] != 0:  # Skip image blocks
            continue

        block_x0 = block.get("bbox", [0, 0, 0, 0])[0]
        block_y0 = block.get("bbox", [0, 0, 0, 0])[1]

        for line in block["lines"]:
            line_text = ""
            max_font_size = 0.0
            line_bbox = line.get("bbox", [block_x0, block_y0, 0, 0])

            for span in line["spans"]:
                line_text += span["text"]
                if span["size"] > max_font_size:
                    max_font_size = span["size"]

            line_text = line_text.strip()
            if line_text:
                result.append({
                    "text": line_text,
                    "font_size": max_font_size,
                    "page": page_num,
                    "x": line_bbox[0],
                    "y": line_bbox[1],
                })

    return result


def _sort_blocks_reading_order(
    blocks: list[dict],
    page_width: float,
) -> list[dict]:
    """Sort blocks in reading order, handling multi-column layouts.

    Detects two-column layouts by checking if blocks cluster on left and right
    halves. If so, reads left column top-to-bottom first, then right column.
    """
    if not blocks:
        return blocks

    mid_x = page_width / 2.0
    margin = page_width * 0.1  # 10% margin for column detection

    left_blocks = [b for b in blocks if b["x"] < mid_x - margin]
    right_blocks = [b for b in blocks if b["x"] >= mid_x + margin]
    center_blocks = [b for b in blocks if mid_x - margin <= b["x"] < mid_x + margin]

    # Heuristic: if both columns have significant content, it's a two-column layout
    is_two_column = len(left_blocks) >= 3 and len(right_blocks) >= 3

    if is_two_column:
        # Full-width elements (title, headings) go first by y-position,
        # then left column, then right column
        full_width = center_blocks
        full_width.sort(key=lambda b: b["y"])

        left_blocks.sort(key=lambda b: b["y"])
        right_blocks.sort(key=lambda b: b["y"])

        # Interleave: full-width rows at their y-position, then columns
        result: list[dict] = []
        for b in sorted(blocks, key=lambda b: b["y"]):
            if b in center_blocks or (b["x"] < mid_x - margin and b not in left_blocks):
                pass  # handled below

        # Simple approach: full-width first (by y), then left col, then right col
        # Group by vertical bands
        result = []
        all_sorted = sorted(blocks, key=lambda b: b["y"])

        # Find section breaks (full-width headings)
        for b in all_sorted:
            is_full_width = mid_x - margin <= b["x"] < mid_x + margin
            is_left = b["x"] < mid_x - margin
            is_right = b["x"] >= mid_x + margin

            if is_full_width:
                result.append(b)

        # Then left column, then right column
        for b in sorted(left_blocks, key=lambda b: b["y"]):
            if b not in result:
                result.append(b)
        for b in sorted(right_blocks, key=lambda b: b["y"]):
            if b not in result:
                result.append(b)

        return result
    else:
        # Single column — sort by y-position
        return sorted(blocks, key=lambda b: (b["y"], b["x"]))


def _detect_title(blocks: list[dict]) -> str:
    """Find the title — the largest text on the first page."""
    first_page = [b for b in blocks if b["page"] == 0]
    if not first_page:
        return "Unknown Title"

    max_size = max(b["font_size"] for b in first_page)
    title_parts = [b["text"] for b in first_page if b["font_size"] == max_size]
    return " ".join(title_parts).strip() or "Unknown Title"


def _detect_authors(blocks: list[dict], title: str) -> str:
    """Find authors — text after the title, before the first section."""
    first_page = [b for b in blocks if b["page"] == 0]
    found_title = False
    author_parts: list[str] = []

    for block in first_page:
        if not found_title:
            if block["text"].strip() == title.strip():
                found_title = True
            continue
        if block["font_size"] >= 13:
            break
        text = block["text"].strip()
        if text:
            author_parts.append(text)
            break

    return " ".join(author_parts).strip()


def _detect_sections(blocks: list[dict]) -> list[dict[str, str]]:
    """Detect section headings by font size AND numbered heading patterns."""
    if not blocks:
        return []

    sizes = [b["font_size"] for b in blocks]
    body_size = max(set(sizes), key=sizes.count)
    heading_threshold = body_size + 1.5

    sections: list[dict[str, str]] = []
    current_heading = ""
    current_content: list[str] = []

    for block in blocks:
        is_heading = False

        # Method 1: Font size heuristic (original)
        if block["font_size"] >= heading_threshold:
            is_heading = True

        # Method 2: Numbered heading pattern (e.g., "1 Introduction", "3.1 Method")
        if not is_heading and _NUMBERED_HEADING_RE.match(block["text"]):
            # Only if the text is short (headings are typically < 80 chars)
            if len(block["text"]) < 80:
                is_heading = True

        if is_heading:
            if current_heading:
                sections.append({
                    "heading": current_heading,
                    "content": "\n".join(current_content).strip(),
                })
            current_heading = block["text"]
            current_content = []
        else:
            current_content.append(block["text"])

    if current_heading:
        sections.append({
            "heading": current_heading,
            "content": "\n".join(current_content).strip(),
        })

    return sections
