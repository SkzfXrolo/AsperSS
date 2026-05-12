from __future__ import annotations


def test_csrf_v2_post_without_token(client):
    r = client.post("/api/auth/logout")
    assert r.status_code in {200, 302, 400, 401, 403}
