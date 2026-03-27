"""E2E tests for Task 2: Frontend UI — dark theme with three-phase layout."""
import subprocess
import time

import pytest
from playwright.sync_api import Page, expect

SCREENSHOTS = "tests/screenshots"


@pytest.fixture(scope="module", autouse=True)
def server():
    """Start the FastAPI server for E2E tests."""
    proc = subprocess.Popen(
        ["uvicorn", "app.main:app", "--host", "127.0.0.1", "--port", "8765"],
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
    )
    time.sleep(2)
    yield proc
    proc.terminate()
    proc.wait()


BASE_URL = "http://127.0.0.1:8765"


def test_page_loads_with_dark_theme(page: Page):
    """Page loads with dark background and correct title."""
    page.goto(BASE_URL)
    page.screenshot(path=f"{SCREENSHOTS}/task2-01-initial-load.png", full_page=True)

    expect(page).to_have_title("Paper-to-Notebook")

    bg_color = page.evaluate(
        "window.getComputedStyle(document.body).backgroundColor"
    )
    assert bg_color in ("rgb(10, 10, 10)", "rgb(10,10,10)"), f"Expected dark bg, got {bg_color}"


def test_api_key_phase_visible(page: Page):
    """Phase 1: API key input and submit button are visible on load."""
    page.goto(BASE_URL)

    api_input = page.locator('[data-testid="api-key-input"]')
    api_button = page.locator('[data-testid="api-key-submit"]')

    expect(api_input).to_be_visible()
    expect(api_button).to_be_visible()

    page.screenshot(path=f"{SCREENSHOTS}/task2-02-api-key-phase.png", full_page=True)


def test_upload_phase_hidden_initially(page: Page):
    """Phase 2: Upload zone is hidden until API key is entered."""
    page.goto(BASE_URL)

    upload_zone = page.locator('[data-testid="upload-zone"]')
    expect(upload_zone).not_to_be_visible()


def test_transition_to_upload_phase(page: Page):
    """Entering an API key transitions to the upload phase."""
    page.goto(BASE_URL)

    page.locator('[data-testid="api-key-input"]').fill("sk-test-key-12345")
    page.locator('[data-testid="api-key-submit"]').click()

    upload_zone = page.locator('[data-testid="upload-zone"]')
    expect(upload_zone).to_be_visible(timeout=3000)

    api_phase = page.locator('[data-testid="phase-api-key"]')
    expect(api_phase).not_to_be_visible()

    page.screenshot(path=f"{SCREENSHOTS}/task2-03-upload-phase.png", full_page=True)


def test_results_phase_elements_exist(page: Page):
    """Phase 3: Results phase has download and Colab buttons (hidden initially)."""
    page.goto(BASE_URL)

    results = page.locator('[data-testid="phase-results"]')
    expect(results).not_to_be_visible()

    download_btn = page.locator('[data-testid="download-btn"]')
    colab_btn = page.locator('[data-testid="colab-btn"]')

    expect(download_btn).not_to_be_visible()
    expect(colab_btn).not_to_be_visible()


def test_status_log_exists(page: Page):
    """Status log area exists for streaming messages."""
    page.goto(BASE_URL)

    status_log = page.locator('[data-testid="status-log"]')
    # It exists in DOM but may be hidden
    assert status_log.count() == 1


def test_responsive_layout(page: Page):
    """Layout looks correct at mobile width."""
    page.set_viewport_size({"width": 375, "height": 812})
    page.goto(BASE_URL)
    page.screenshot(path=f"{SCREENSHOTS}/task2-04-mobile-view.png", full_page=True)

    api_input = page.locator('[data-testid="api-key-input"]')
    expect(api_input).to_be_visible()


def test_inter_font_loaded(page: Page):
    """Inter font is specified in CSS."""
    page.goto(BASE_URL)

    font_family = page.evaluate(
        "window.getComputedStyle(document.body).fontFamily"
    )
    assert "Inter" in font_family or "inter" in font_family.lower(), (
        f"Expected Inter font, got {font_family}"
    )
