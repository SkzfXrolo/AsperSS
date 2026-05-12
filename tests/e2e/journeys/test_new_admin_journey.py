from __future__ import annotations

import pytest


@pytest.mark.e2e
def test_new_admin_journey_smoke(page, base_url):
    page.goto(base_url)
    assert page.locator("body").count() == 1
