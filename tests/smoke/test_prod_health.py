from __future__ import annotations

import os

import pytest
import requests


BASE = os.getenv("ARGUS_PROD_URL")


@pytest.mark.smoke
def test_prod_health_detailed():
    if not BASE:
        pytest.skip("ARGUS_PROD_URL no configurado")
    r = requests.get(f"{BASE}/health", timeout=20)
    assert r.status_code == 200
    assert r.text.strip()
