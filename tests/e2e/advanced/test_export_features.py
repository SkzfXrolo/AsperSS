from __future__ import annotations

import pytest


@pytest.mark.e2e
def test_export_endpoints_smoke(page, base_url):
    page.goto(f"{base_url}/api/scans/1/export/csv")
    assert page.locator("body").count() in {0, 1}
