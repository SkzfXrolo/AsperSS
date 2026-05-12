from __future__ import annotations

import pytest


@pytest.mark.e2e
def test_offline_support_placeholder(page, base_url):
    page.goto(base_url)
    page.context.set_offline(True)
    assert page.url.startswith("http")
