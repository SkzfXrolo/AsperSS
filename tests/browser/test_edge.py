from __future__ import annotations

import pytest


@pytest.mark.e2e
@pytest.mark.parametrize("w,h", [(1366, 768), (1920, 1080)])
def test_edge_resolution_smoke(page, base_url, w, h):
    page.set_viewport_size({"width": w, "height": h})
    page.goto(base_url)
    assert page.locator("html").count() == 1
