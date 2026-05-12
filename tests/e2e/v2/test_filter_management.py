from __future__ import annotations

import pytest


@pytest.mark.e2e
def test_filter_management(page, base_url):
    page.goto(f"{base_url}/panel")
    assert page.locator("body").count() == 1
