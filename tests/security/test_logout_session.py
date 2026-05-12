from __future__ import annotations


def test_logout_invalidates_cookie_and_session(login_session):
    r = login_session.post("/api/auth/logout")
    assert r.status_code == 200
    set_cookie = r.headers.get("Set-Cookie", "")
    assert "session=" in set_cookie.lower()
    assert "max-age=0" in set_cookie.lower() or "expires=" in set_cookie.lower()
    assert "no-store" in (r.headers.get("Cache-Control") or "")

    with login_session.session_transaction() as sess:
        assert "user_id" not in sess
