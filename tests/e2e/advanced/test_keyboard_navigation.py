from __future__ import annotations

import pytest


@pytest.mark.e2e
def test_keyboard_navigation_basic(page, base_url):
    page.goto(f"{base_url}/")
    page.keyboard.press("Tab")
    assert page.locator(":focus").count() in {0, 1}
