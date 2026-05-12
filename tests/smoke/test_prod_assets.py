from __future__ import annotations

import os

import pytest
import requests


BASE = os.getenv("ARGUS_PROD_URL")


@pytest.mark.smoke
@pytest.mark.parametrize("path", ["/static/css/argus-ui.css", "/favicon.ico"])
def test_prod_assets_head(path):
    if not BASE:
        pytest.skip("ARGUS_PROD_URL no configurado")
    r = requests.head(f"{BASE}{path}", timeout=20, allow_redirects=True)
    assert r.status_code in {200, 301, 302}
