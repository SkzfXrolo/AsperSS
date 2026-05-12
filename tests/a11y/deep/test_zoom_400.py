from __future__ import annotations

import pytest


@pytest.mark.e2e
def test_zoom_400_layout(page, base_url):
    page.goto(base_url)
    page.set_viewport_size({"width": 320, "height": 900})
    assert page.locator("body").count() == 1
