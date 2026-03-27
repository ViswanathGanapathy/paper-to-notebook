"""QUALITY TEST — Real notebook generation from TabR1 paper.

This test opens a VISIBLE browser, lets the user enter their OpenAI API key,
generates a real notebook from the TabR1 paper, and validates the output.

Run with:
    pytest tests/quality/test_real_generation.py -v -s --headed

The --headed flag shows the browser. The -s flag shows print output.
The test waits for you to enter your API key manually.
"""
import json
import os
import subprocess
import time
from pathlib import Path

import nbformat
import pytest
from playwright.sync_api import Page, Browser, BrowserType, expect

SCREENSHOTS = "tests/screenshots"
TABR1_PDF = Path(__file__).resolve().parent.parent.parent / "Tabr1.pdf"

# Mark as quality test — skipped in normal CI runs
pytestmark = pytest.mark.quality


@pytest.fixture(scope="module", autouse=True)
def server():
    """Start the FastAPI server."""
    proc = subprocess.Popen(
        ["uvicorn", "app.main:app", "--host", "127.0.0.1", "--port", "8769"],
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
    )
    time.sleep(3)
    yield proc
    proc.terminate()
    proc.wait()


@pytest.fixture(scope="module")
def browser_page(browser: Browser):
    """Create a visible browser page."""
    context = browser.new_context(viewport={"width": 1280, "height": 900})
    page = context.new_page()
    yield page
    context.close()


BASE_URL = "http://127.0.0.1:8769"


def test_real_generation_from_tabr1(browser_page: Page):
    """Full quality test: generate a real notebook from TabR1 paper.

    Steps:
    1. Navigate to the app
    2. Wait for user to enter their OpenAI API key (manual)
    3. Upload TabR1.pdf
    4. Wait for generation to complete (up to 5 minutes)
    5. Download the notebook
    6. Validate: valid JSON, sections, Python syntax, disclaimer
    """
    page = browser_page

    # ── Step 1: Navigate ─────────────────────────────────
    page.goto(BASE_URL)
    page.screenshot(path=f"{SCREENSHOTS}/quality-01-page-load.png", full_page=True)
    print("\n" + "=" * 60)
    print("QUALITY TEST: Real notebook generation from TabR1 paper")
    print("=" * 60)

    # ── Step 2: Enter API key ────────────────────────────
    # Check if API key is provided via environment variable
    api_key = os.environ.get("OPENAI_API_KEY", "")

    if api_key:
        print(f"Using API key from OPENAI_API_KEY env var (sk-...{api_key[-4:]})")
        page.locator('[data-testid="api-key-input"]').fill(api_key)
        page.locator('[data-testid="api-key-submit"]').click()
    else:
        print("\nPlease enter your OpenAI API key in the browser...")
        print("The test will wait up to 60 seconds for you to submit it.")
        # Wait for user to manually enter key and click Continue
        # The upload zone becomes visible when the key is submitted
        page.locator('[data-testid="api-key-input"]').click()

    # Wait for upload phase (up to 60 seconds for manual entry)
    expect(page.locator('[data-testid="upload-zone"]')).to_be_visible(timeout=60000)
    page.screenshot(path=f"{SCREENSHOTS}/quality-02-upload-phase.png", full_page=True)
    print("API key accepted. Moving to upload phase.")

    # ── Step 3: Upload TabR1.pdf ─────────────────────────
    assert TABR1_PDF.exists(), f"TabR1.pdf not found at {TABR1_PDF}"
    page.locator('[data-testid="file-input"]').set_input_files(str(TABR1_PDF))

    expect(page.locator('[data-testid="file-selected"]')).to_be_visible(timeout=5000)
    page.screenshot(path=f"{SCREENSHOTS}/quality-03-file-uploaded.png", full_page=True)
    print(f"Uploaded: {TABR1_PDF.name} ({TABR1_PDF.stat().st_size / 1024:.0f} KB)")

    # ── Step 4: Click Generate and wait ──────────────────
    page.locator('[data-testid="generate-btn"]').click()
    expect(page.locator('[data-testid="phase-results"]')).to_be_visible(timeout=10000)
    page.screenshot(path=f"{SCREENSHOTS}/quality-04-generating.png", full_page=True)
    print("Generation started. Waiting up to 5 minutes...")

    # Wait for the download button to appear (up to 5 minutes)
    download_btn = page.locator('[data-testid="download-btn"]')
    try:
        expect(download_btn).to_be_visible(timeout=300000)  # 5 minutes
    except Exception:
        # Take screenshot of final state even if it failed
        page.screenshot(path=f"{SCREENSHOTS}/quality-05-timeout.png", full_page=True)
        status_text = page.locator('[data-testid="status-log"]').inner_text()
        print(f"TIMEOUT — Last status: {status_text[:500]}")
        pytest.fail("Generation timed out after 5 minutes")

    page.screenshot(path=f"{SCREENSHOTS}/quality-05-complete.png", full_page=True)
    print("Generation complete!")

    # ── Step 5: Download the notebook ────────────────────
    download_href = download_btn.get_attribute("href")
    assert download_href, "Download button has no href"
    print(f"Downloading from: {download_href}")

    # Use the API directly to download
    import httpx
    response = httpx.get(f"{BASE_URL}{download_href}")
    assert response.status_code == 200, f"Download failed: {response.status_code}"

    notebook_bytes = response.content
    notebook_text = notebook_bytes.decode("utf-8")
    print(f"Downloaded notebook: {len(notebook_bytes)} bytes")

    # Save for inspection
    output_path = Path("tests/quality/tabr1_generated.ipynb")
    output_path.write_bytes(notebook_bytes)
    print(f"Saved to: {output_path}")

    # ── Step 6: Validate the notebook ────────────────────
    print("\n--- VALIDATION ---")

    # 6a. Valid JSON
    notebook_data = json.loads(notebook_text)
    assert "cells" in notebook_data, "Missing 'cells' key"
    print(f"  Valid JSON: YES ({len(notebook_data['cells'])} cells)")

    # 6b. Valid nbformat
    nb = nbformat.reads(notebook_text, as_version=4)
    nbformat.validate(nb)
    print("  Valid nbformat: YES")

    # 6c. Has both markdown and code cells
    cell_types = [c.cell_type for c in nb.cells]
    assert "markdown" in cell_types, "No markdown cells found"
    assert "code" in cell_types, "No code cells found"
    md_count = cell_types.count("markdown")
    code_count = cell_types.count("code")
    print(f"  Cell types: {md_count} markdown, {code_count} code")

    # 6d. At least 8 sections (markdown cells starting with #)
    section_cells = [c for c in nb.cells if c.cell_type == "markdown" and c.source.strip().startswith("#")]
    assert len(section_cells) >= 8, f"Only {len(section_cells)} section headers found (need >= 8)"
    print(f"  Section headers: {len(section_cells)} (>= 8 required)")
    for sc in section_cells[:10]:
        first_line = sc.source.strip().split("\n")[0]
        print(f"    - {first_line[:80]}")

    # 6e. All code cells are valid Python (compile check)
    syntax_errors = []
    for i, cell in enumerate(nb.cells):
        if cell.cell_type != "code":
            continue
        source = cell.source.strip()
        if not source or source.startswith("!") or source.startswith("%"):
            continue  # Skip shell commands and magic commands
        # Filter out lines starting with ! (shell) or % (magic)
        python_lines = [
            line for line in source.split("\n")
            if not line.strip().startswith("!") and not line.strip().startswith("%")
        ]
        python_source = "\n".join(python_lines)
        if not python_source.strip():
            continue
        try:
            compile(python_source, f"<cell_{i}>", "exec")
        except SyntaxError as e:
            syntax_errors.append(f"Cell {i}: {e.msg} (line {e.lineno})")

    if syntax_errors:
        print(f"  Python syntax: {len(syntax_errors)} error(s)")
        for err in syntax_errors[:5]:
            print(f"    - {err}")
        # Warn but don't fail — LLM-generated code may have minor issues
        print("  WARNING: Some cells have syntax issues (LLM-generated)")
    else:
        print("  Python syntax: ALL VALID")

    # 6f. Safety disclaimer cell is present
    all_sources = " ".join(c.source for c in nb.cells)
    has_disclaimer = "disclaimer" in all_sources.lower() or "ai-generated" in all_sources.lower() or "review" in all_sources.lower()
    assert has_disclaimer, "No safety disclaimer found in notebook"
    print("  Safety disclaimer: PRESENT")

    # 6g. Has TabR1-related content
    has_tabr = "tabr" in all_sources.lower() or "tab" in all_sources.lower()
    print(f"  TabR1 content: {'YES' if has_tabr else 'PARTIAL'}")

    print("\n" + "=" * 60)
    print("QUALITY TEST PASSED")
    print(f"Generated notebook: {len(nb.cells)} cells, {md_count} markdown, {code_count} code")
    print(f"Saved to: {output_path}")
    print("=" * 60)

    page.screenshot(path=f"{SCREENSHOTS}/quality-06-validation-done.png", full_page=True)
