"""Pipeline orchestrator — ties together PDF extraction, LLM analysis, and notebook building.

Yields SSE-compatible status messages at each stage.
"""
import json
import logging
import uuid
from pathlib import Path
from typing import Any, AsyncGenerator

from openai import AsyncOpenAI

from app.notebook_builder import build_notebook
from app.pdf_extractor import PDFExtractionError, extract_pdf
from app.llm_generator import analyze_paper, generate_notebook_cells

logger = logging.getLogger(__name__)

GENERATED_DIR = Path(__file__).resolve().parent.parent / "generated"
GENERATED_DIR.mkdir(exist_ok=True)


async def run_pipeline(
    api_key: str,
    pdf_bytes: bytes,
    filename: str,
) -> AsyncGenerator[dict[str, str], None]:
    """Run the full paper-to-notebook pipeline, yielding SSE events.

    Yields dicts with 'event' and 'data' keys suitable for SSE.
    Events: 'status' (progress updates), 'complete' (final result), 'error' (failure).
    """

    # ── Stage 1: PDF Extraction ──────────────────────────
    safe_filename = _sanitize_filename(filename)
    yield _status(f"Extracting text from {safe_filename}...")

    try:
        paper_data = extract_pdf(pdf_bytes)
    except PDFExtractionError as exc:
        yield _error(str(exc))
        return

    title = paper_data.get("title", "Unknown Paper")
    authors = paper_data.get("authors", "")
    page_count = paper_data.get("page_count", 0)
    section_count = len(paper_data.get("sections", []))

    yield _status(
        f"Extracted {page_count} pages with {section_count} sections. "
        f"Paper: \"{title}\""
    )

    # ── Stage 2: Paper Analysis (LLM Phase 1) ───────────
    yield _status("Analyzing paper structure — identifying algorithms, equations, and methodology...")

    client = AsyncOpenAI(api_key=api_key)

    try:
        analysis = await analyze_paper(client, paper_data["full_text"])
    except Exception as exc:
        yield _error(f"Analysis failed: {_sanitize_error(exc)}")
        return

    algo_names = [a.get("name", "?") for a in analysis.get("key_algorithms", [])]
    if algo_names:
        yield _status(
            f"Identified {len(algo_names)} key algorithm(s): {', '.join(algo_names)}"
        )

    methodology = analysis.get("methodology", [])
    if methodology:
        yield _status(
            f"Methodology: {'; '.join(methodology[:3])}"
            + ("..." if len(methodology) > 3 else "")
        )

    # ── Stage 3: Notebook Generation (LLM Phase 2) ──────
    yield _status("Generating research-grade implementation notebook — this may take a minute...")

    try:
        cells = await generate_notebook_cells(client, analysis, paper_data["full_text"])
    except Exception as exc:
        yield _error(f"Generation failed: {_sanitize_error(exc)}")
        return

    code_cells = sum(1 for c in cells if c.get("cell_type") == "code")
    md_cells = sum(1 for c in cells if c.get("cell_type") == "markdown")
    yield _status(f"Generated {len(cells)} cells ({code_cells} code, {md_cells} markdown)")

    # ── Stage 4: Notebook Assembly ───────────────────────
    yield _status("Assembling .ipynb notebook with Colab metadata...")

    paper_meta: dict[str, Any] = {"title": title, "authors": authors}

    try:
        notebook_bytes = build_notebook(cells, paper_meta)
    except Exception as exc:
        yield _error(_sanitize_error(exc))
        return

    # Save to generated/ directory
    file_id = str(uuid.uuid4())
    output_path = GENERATED_DIR / f"{file_id}.ipynb"
    output_path.write_bytes(notebook_bytes)

    yield _status("Notebook ready for download!")
    yield _complete(file_id, title)


def _status(message: str) -> dict[str, str]:
    return {"event": "status", "data": json.dumps({"message": message})}


def _error(message: str) -> dict[str, str]:
    return {"event": "error", "data": json.dumps({"message": message})}


def _complete(file_id: str, title: str) -> dict[str, str]:
    # Build Colab URL using our notebook JSON endpoint
    # When deployed, the frontend will substitute the real base URL
    notebook_path = f"/api/notebook/{file_id}"
    colab_url = f"https://colab.research.google.com/url={{BASE_URL}}{notebook_path}"

    return {
        "event": "complete",
        "data": json.dumps({
            "file_id": file_id,
            "title": title,
            "colab_url": colab_url,
            "notebook_path": notebook_path,
        }),
    }


def _sanitize_error(exc: Exception) -> str:
    """Return a user-safe error message without leaking internals."""
    import asyncio
    import traceback

    # asyncio.TimeoutError has an empty str() — check type first
    if isinstance(exc, (asyncio.TimeoutError, TimeoutError)):
        return "Request timed out. The paper may be too complex. Please try a shorter paper or try again."

    msg = str(exc)
    exc_type = type(exc).__name__

    if "api_key" in msg.lower() or "authentication" in msg.lower() or "401" in msg:
        return "Invalid or expired API key. Please check your OpenAI API key."
    if "rate" in msg.lower() and "limit" in msg.lower():
        return "OpenAI rate limit exceeded. Please wait a moment and try again."
    if "timeout" in msg.lower():
        return "Request timed out. The paper may be too long. Try a shorter paper."
    if "connection" in msg.lower() or "network" in msg.lower():
        return "Network error connecting to OpenAI. Please check your connection and try again."
    if "json" in msg.lower() or "decode" in msg.lower():
        return "Failed to parse the AI response. Please try again."

    # Generic fallback — log full details server-side, return safe message
    logger.error("Unhandled pipeline error [%s]: %s", exc_type, msg)
    logger.error("Traceback:\n%s", "".join(traceback.format_exception(type(exc), exc, exc.__traceback__)))
    return "An unexpected error occurred during processing. Please try again."


def _sanitize_filename(filename: str) -> str:
    """Sanitize a filename before reflecting it in status messages (SEC-012)."""
    import re
    # Strip HTML/script tags
    safe = re.sub(r"<[^>]*>", "", filename)
    # Keep only safe characters
    safe = re.sub(r"[^\w\s\-_.\(\)]", "", safe)
    # Truncate
    if len(safe) > 100:
        safe = safe[:97] + "..."
    return safe.strip() or "uploaded file"
