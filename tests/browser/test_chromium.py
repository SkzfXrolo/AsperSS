from __future__ import annotations

import pytest


@pytest.mark.e2e
def test_chromium_smoke(page, base_url):
    page.goto(base_url)
    assert page.title() is not None
