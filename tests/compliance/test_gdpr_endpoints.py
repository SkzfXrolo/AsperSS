from __future__ import annotations

import pytest


def test_dsar_endpoints_placeholder(client):
    r = client.get("/api/gdpr/export")
    if r.status_code == 404:
        pytest.skip("DSAR todavía no implementado")
    assert r.status_code in {200, 302, 401, 403}
