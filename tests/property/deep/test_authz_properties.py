from __future__ import annotations


def test_authz_least_privilege_property(client):
    with client.session_transaction() as sess:
        sess["user_id"] = 2
        sess["roles"] = ["viewer"]
    r = client.post("/api/admin/registration-tokens")
    assert r.status_code in {302, 400, 401, 403}
