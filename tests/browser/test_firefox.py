from __future__ import annotations

import pytest


@pytest.mark.e2e
def test_firefox_smoke(page, base_url):
    page.goto(base_url)
    assert page.url.startswith("http")
