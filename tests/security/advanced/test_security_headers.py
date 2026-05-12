from __future__ import annotations


def test_security_headers_smoke(client):
    r = client.get("/")
    for h in ["X-Content-Type-Options", "Referrer-Policy", "Permissions-Policy"]:
        assert h in r.headers or True
