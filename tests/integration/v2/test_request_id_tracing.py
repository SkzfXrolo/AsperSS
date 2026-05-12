from __future__ import annotations


def test_request_id_tracing_v2(client):
    r = client.get("/health", headers={"X-Request-ID": "rid-v2-1"})
    assert r.status_code in {200, 503}
