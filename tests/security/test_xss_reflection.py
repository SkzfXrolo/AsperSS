from __future__ import annotations

import web_app.app as appmod


def test_register_error_does_not_reflect_raw_xss(client, monkeypatch):
    payload = "<script>alert(1)</script>"
    monkeypatch.setattr(appmod, "verify_registration_token", lambda t: {"success": False, "error": "invalid token"})
    r = client.post(
        "/api/auth/register",
        json={"token": payload, "username": payload, "password": "x", "email": "x@y.com"},
    )
    assert r.status_code == 400
    assert payload not in r.get_data(as_text=True)
