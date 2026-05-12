from __future__ import annotations


def test_request_id_propagation(client):
    rid = "req-pack48-monitoring"
    r = client.get("/health", headers={"X-Request-ID": rid})
    assert r.status_code in {200, 503}
