from __future__ import annotations


def test_health_endpoint(client):
    r = client.get("/health")
    assert r.status_code == 200


def test_api_version_endpoint(client):
    r = client.get("/api/version")
    assert r.status_code == 200


def test_api_status_like_endpoint(client):
    # Algunas ramas exponen /api/status y otras /api/db-status.
    r = client.get("/api/status")
    if r.status_code == 404:
        r = client.get("/api/db-status")
    assert r.status_code in {200, 503}
