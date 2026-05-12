from __future__ import annotations

import pytest


@pytest.mark.e2e
def test_polyfills_loaded(page, base_url):
    page.goto(base_url)
    assert page.evaluate("() => typeof Promise !== 'undefined'")
