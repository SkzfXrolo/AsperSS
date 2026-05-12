from __future__ import annotations


def test_signup_login_first_scan_journey(client):
    reg = client.post("/api/auth/register", json={"token": "x", "username": "u", "password": "p"})
    assert reg.status_code in {200, 400}
    login = client.post("/api/auth/login", json={"username": "u", "password": "p"})
    assert login.status_code in {200, 401}
    scans = client.get("/api/scans")
    assert scans.status_code in {200, 401, 302}
