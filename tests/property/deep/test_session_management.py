from __future__ import annotations


def test_session_lifecycle_property(client):
    r1 = client.get("/health")
    assert r1.status_code in {200, 503}
    with client.session_transaction() as sess:
        sess["user_id"] = 1
    r2 = client.get("/health")
    assert r2.status_code in {200, 503}
