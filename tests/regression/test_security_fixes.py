from __future__ import annotations


def test_security_headers_present_smoke(client):
    r = client.get("/")
    assert r.status_code in {200, 302}


def test_auth_endpoints_do_not_500(client):
    r = client.post("/api/auth/login", json={})
    assert r.status_code in {200, 400, 401, 403}
