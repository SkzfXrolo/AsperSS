from __future__ import annotations

import pytest


@pytest.mark.e2e
def test_superadmin_sections_load(page, base_url):
    page.goto(f"{base_url}/aspers-sa")
    assert page.locator("body").count() == 1
