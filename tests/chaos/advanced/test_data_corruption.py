from __future__ import annotations

import pytest


@pytest.mark.chaos
def test_data_corruption_smoke(client):
    r = client.post("/api/oracle/evaluate", data=b"\x00\x01")
    assert r.status_code in {200, 400, 415, 500}
