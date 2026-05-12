from __future__ import annotations


def test_clickjacking_headers(client):
    r = client.get("/")
    xfo = r.headers.get("X-Frame-Options", "")
    csp = r.headers.get("Content-Security-Policy", "")
    assert isinstance(xfo, str)
    assert isinstance(csp, str)
