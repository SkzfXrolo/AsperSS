from __future__ import annotations

import pytest


@pytest.mark.e2e
def test_free_to_pro_upgrade_smoke(page, base_url):
    page.goto(f"{base_url}/pricing")
    assert page.locator("body").count() == 1
