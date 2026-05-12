from __future__ import annotations

import pytest


def test_oauth_flow_placeholder(client):
    r = client.get("/api/oauth/callback?code=fake")
    if r.status_code == 404:
        pytest.skip("OAuth flow no implementado")
    assert r.status_code in {200, 400, 401, 403}
