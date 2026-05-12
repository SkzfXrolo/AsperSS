from __future__ import annotations

import web_app.app as appmod


def test_api_login_success_sets_session(client, monkeypatch):
    monkeypatch.setattr(
        appmod,
        "authenticate_user",
        lambda u, p: {"success": True, "user": {"id": 5, "username": u, "roles": ["user"], "company_id": 1}},
    )
    r = client.post("/api/auth/login", json={"username": "u", "password": "p"})
    assert r.status_code == 200
    with client.session_transaction() as sess:
        assert sess.get("user_id") == 5


def test_api_logout_invalidates_session_and_sets_cache_headers(login_session):
    r = login_session.post("/api/auth/logout")
    assert r.status_code in {200, 400}
    if r.status_code == 200:
        assert "no-store" in (r.headers.get("Cache-Control") or "")
    with login_session.session_transaction() as sess:
        assert "user_id" not in sess


def test_api_register_success(client, monkeypatch):
    monkeypatch.setattr(appmod, "verify_registration_token", lambda t: {"success": True, "created_by": 1, "company_id": None})
    monkeypatch.setattr(appmod, "create_user", lambda **kwargs: {"success": True})
    r = client.post(
        "/api/auth/register",
        json={"token": "abc", "username": "new", "password": "pw", "email": "a@b.com"},
    )
    assert r.status_code == 200


def test_api_register_invalid_token(client, monkeypatch):
    monkeypatch.setattr(appmod, "verify_registration_token", lambda t: {"success": False, "error": "bad token"})
    r = client.post("/api/auth/register", json={"token": "bad", "username": "new", "password": "pw"})
    assert r.status_code == 400
