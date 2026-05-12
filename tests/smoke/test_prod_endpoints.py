from __future__ import annotations

import os

import pytest
import requests


BASE = os.getenv("ARGUS_PROD_URL")


@pytest.mark.smoke
@pytest.mark.parametrize("path", ["/", "/health", "/api/version"])
def test_prod_public_endpoints(path):
    if not BASE:
        pytest.skip("ARGUS_PROD_URL no configurado para smoke")
    r = requests.get(f"{BASE}{path}", timeout=20)
    assert r.status_code in {200, 301, 302}
