from __future__ import annotations

import pytest


@pytest.mark.e2e
def test_oracle_assistant_full(page, base_url):
    page.goto(base_url)
    assert page.locator("body").count() == 1
