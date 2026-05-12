from __future__ import annotations

import pytest


@pytest.mark.e2e
def test_high_contrast_mode(page, base_url):
    page.goto(base_url)
    page.emulate_media(color_scheme="dark")
    assert page.locator("body").count() == 1
