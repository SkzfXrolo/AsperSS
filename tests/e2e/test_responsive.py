from __future__ import annotations

import pytest


@pytest.mark.e2e
@pytest.mark.parametrize("size", [{"width": 375, "height": 812}, {"width": 768, "height": 1024}, {"width": 1440, "height": 900}])
def test_responsive_no_horizontal_overflow(page, base_url, size):
    page.set_viewport_size(size)
    page.goto(f"{base_url}/")
    overflow = page.evaluate("() => document.documentElement.scrollWidth > window.innerWidth")
    assert overflow is False
