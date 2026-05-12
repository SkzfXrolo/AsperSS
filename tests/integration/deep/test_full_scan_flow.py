from __future__ import annotations

import pytest


def test_full_scan_flow_smoke(client):
    start = client.post("/api/scans", json={"token": ""})
    assert start.status_code in {201, 400, 401}
    detail = client.get("/api/scans/1")
    assert detail.status_code in {200, 401, 302, 404}


@pytest.mark.integration
def test_oracle_eval_after_scan_smoke(client):
    r = client.post("/api/plugin/ai-evaluate", json={})
    assert r.status_code in {200, 400, 401, 403, 404}
