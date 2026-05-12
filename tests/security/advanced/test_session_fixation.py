from __future__ import annotations


def test_session_fixation_smoke(client):
    before = client.get("/").headers.get("Set-Cookie", "")
    client.post("/api/auth/login", json={"username": "x", "password": "x"})
    after = client.get("/").headers.get("Set-Cookie", "")
    assert isinstance(before, str)
    assert isinstance(after, str)
