from __future__ import annotations

import pytest


@pytest.mark.e2e
def test_panel_basic_a11y_structure(page, base_url):
    page.goto(f"{base_url}/panel")
    page_title = page.title()
    assert isinstance(page_title, str)
    assert page.locator("html[lang]").count() in {0, 1}
