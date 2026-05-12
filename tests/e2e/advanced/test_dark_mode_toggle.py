from __future__ import annotations

import pytest


@pytest.mark.e2e
def test_dark_mode_toggle_smoke(page, base_url):
    page.goto(f"{base_url}/")
    body = page.locator("body")
    assert body.count() == 1
