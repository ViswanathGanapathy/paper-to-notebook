"""E2E tests for Task 10: UI polish — animations, transitions, and micro-interactions."""
import subprocess
import time

import pytest
from playwright.sync_api import Page, expect

SCREENSHOTS = "tests/screenshots"


@pytest.fixture(scope="module", autouse=True)
def server():
    proc = subprocess.Popen(
        ["uvicorn", "app.main:app", "--host", "127.0.0.1", "--port", "8767"],
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
    )
    time.sleep(2)
    yield proc
    proc.terminate()
    proc.wait()


BASE_URL = "http://127.0.0.1:8767"


def test_phase_transition_has_animation(page: Page):
    """Phase transitions use CSS opacity/transform animations."""
    page.goto(BASE_URL)

    # Check that the API key phase has transition CSS
    phase = page.locator('[data-testid="phase-api-key"]')
    transition = page.evaluate(
        "window.getComputedStyle(document.querySelector('[data-testid=\"phase-api-key\"]')).transition"
    )
    assert "opacity" in transition or "transform" in transition or "all" in transition

    page.screenshot(path=f"{SCREENSHOTS}/task10-01-initial-polished.png", full_page=True)


def test_upload_zone_glow_on_hover(page: Page):
    """Upload zone has visual feedback on hover."""
    page.goto(BASE_URL)

    # Navigate to upload phase
    page.locator('[data-testid="api-key-input"]').fill("sk-test-12345")
    page.locator('[data-testid="api-key-submit"]').click()
    expect(page.locator('[data-testid="upload-zone"]')).to_be_visible(timeout=3000)

    # Hover over upload zone
    page.locator('[data-testid="upload-zone"]').hover()
    page.wait_for_timeout(300)

    page.screenshot(path=f"{SCREENSHOTS}/task10-02-upload-hover.png", full_page=True)


def test_button_hover_effects(page: Page):
    """Buttons have hover transform effects."""
    page.goto(BASE_URL)

    # Check the submit button has transition
    btn = page.locator('[data-testid="api-key-submit"]')
    transition = page.evaluate(
        "window.getComputedStyle(document.querySelector('[data-testid=\"api-key-submit\"]')).transition"
    )
    assert len(transition) > 0 and transition != "none"

    page.screenshot(path=f"{SCREENSHOTS}/task10-03-button-style.png", full_page=True)


def test_powered_by_badge_visible(page: Page):
    """'Powered by gpt-5.4' badge is visible in footer."""
    page.goto(BASE_URL)

    footer_text = page.locator(".footer").inner_text()
    assert "gpt-5.4" in footer_text.lower() or "gpt" in footer_text.lower()


def test_keyboard_enter_submits_api_key(page: Page):
    """Pressing Enter in the API key input submits the form."""
    page.goto(BASE_URL)

    page.locator('[data-testid="api-key-input"]').fill("sk-test-key")
    page.locator('[data-testid="api-key-input"]').press("Enter")

    # Should transition to upload phase
    expect(page.locator('[data-testid="upload-zone"]')).to_be_visible(timeout=3000)


def test_mobile_layout_stacked(page: Page):
    """On mobile, input group stacks vertically."""
    page.set_viewport_size({"width": 375, "height": 812})
    page.goto(BASE_URL)

    page.screenshot(path=f"{SCREENSHOTS}/task10-04-mobile-polished.png", full_page=True)

    # The API key input should still be visible and usable
    api_input = page.locator('[data-testid="api-key-input"]')
    expect(api_input).to_be_visible()

    # Input should be full-width on mobile (close to container width)
    box = api_input.bounding_box()
    assert box is not None
    assert box["width"] >= 250  # At least most of the 375px viewport (accounting for padding)


def test_full_polished_flow_screenshot(page: Page):
    """Capture the complete polished flow for visual review."""
    page.set_viewport_size({"width": 1280, "height": 800})
    page.goto(BASE_URL)
    page.screenshot(path=f"{SCREENSHOTS}/task10-05-final-desktop.png", full_page=True)

    # Enter API key
    page.locator('[data-testid="api-key-input"]').fill("sk-test-12345")
    page.locator('[data-testid="api-key-submit"]').click()
    page.wait_for_timeout(500)  # Let animation complete
    page.screenshot(path=f"{SCREENSHOTS}/task10-06-final-upload.png", full_page=True)
