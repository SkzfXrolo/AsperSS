from __future__ import annotations


def test_health_endpoint_idempotency(client):
    a = client.get("/health")
    b = client.get("/health")
    assert a.status_code == b.status_code
