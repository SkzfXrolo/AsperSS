from __future__ import annotations

import pytest


@pytest.mark.chaos
def test_external_api_down_smoke(client):
    # endpoint típico que podría depender de servicios externos
    r = client.get("/api/version")
    assert r.status_code in {200, 500, 503}
