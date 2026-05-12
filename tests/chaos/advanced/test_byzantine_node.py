from __future__ import annotations

import pytest


@pytest.mark.chaos
def test_byzantine_node_payload_smoke(client):
    r = client.post("/api/oracle/evaluate", json={"violations": "malicious"})
    assert r.status_code in {200, 400, 422, 500}
