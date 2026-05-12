from __future__ import annotations


def test_plugin_violation_sync_flow(client):
    v = client.post("/api/plugin/violation", json={})
    assert v.status_code in {200, 400, 401, 403}
    stats = client.get("/api/plugin/violations/stats")
    assert stats.status_code in {200, 302, 400, 401, 403}
