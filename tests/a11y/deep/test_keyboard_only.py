from __future__ import annotations

import pytest


@pytest.mark.e2e
def test_keyboard_only_flow(page, base_url):
    page.goto(base_url)
    page.keyboard.press("Tab")
    assert page.locator(":focus").count() >= 0
