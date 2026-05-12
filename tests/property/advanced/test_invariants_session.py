from __future__ import annotations


def test_session_create_use_logout(login_session):
    with login_session.session_transaction() as sess:
        assert "user_id" in sess
    r = login_session.get("/logout")
    assert r.status_code in {200, 302}
    with login_session.session_transaction() as sess:
        assert "user_id" not in sess
