from __future__ import annotations

import os

import pytest
import requests


BASE = os.getenv("ARGUS_PROD_URL")


@pytest.mark.smoke
def test_prod_robots_and_sitemap():
    if not BASE:
        pytest.skip("ARGUS_PROD_URL no configurado")
    robots = requests.get(f"{BASE}/robots.txt", timeout=20)
    sitemap = requests.get(f"{BASE}/sitemap.xml", timeout=20)
    assert robots.status_code in {200, 404}
    assert sitemap.status_code in {200, 404}
