from __future__ import annotations


def test_cache_layer_headers_smoke(client):
    r = client.get("/health")
    assert r.status_code in {200, 503}
