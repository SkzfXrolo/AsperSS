from __future__ import annotations

import pytest
import requests


@pytest.mark.e2e
def test_scan_creation_flow_smoke(page, base_url):
    page.goto(f"{base_url}/")
    assert page.locator("body").count() == 1
    r = requests.post(f"{base_url}/api/scans", json={"token": ""}, timeout=10)
    assert r.status_code in {201, 400, 401}
