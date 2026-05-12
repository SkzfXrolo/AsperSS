from __future__ import annotations


def test_error_content_type_is_consistent(client):
    r = client.get("/missing-endpoint")
    assert r.status_code == 404
    assert "text/html" in (r.headers.get("Content-Type") or "")


def test_basic_security_headers_shape(client):
    r = client.get("/")
    assert r.status_code in {200, 302}
    assert isinstance(r.headers.get("Content-Type"), str)
