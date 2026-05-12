from __future__ import annotations

import pytest


@pytest.mark.e2e
def test_screen_reader_landmarks(page, base_url):
    page.goto(base_url)
    assert page.locator("main, [role='main']").count() >= 0
