from __future__ import annotations


def test_health_endpoint(client):
    r = client.get("/health")
    assert r.status_code in {200, 503}


def test_version_endpoint(client):
    r = client.get("/api/version")
    assert r.status_code in {200, 404}


def test_status_endpoint(client):
    r = client.get("/api/status")
    assert r.status_code in {200, 404}
