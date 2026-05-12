from __future__ import annotations


def test_post_scans_without_token_fails(client):
    r = client.post("/api/scans", json={})
    assert r.status_code in {400, 401}


def test_get_scans_requires_auth(client):
    r = client.get("/api/scans")
    assert r.status_code in {401, 302}


def test_get_single_scan_requires_auth(client):
    r = client.get("/api/scans/1")
    assert r.status_code in {401, 302}
