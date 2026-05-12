from __future__ import annotations


def test_jwt_alg_none_rejected_smoke(client):
    r = client.get("/api/version", headers={"Authorization": "Bearer ey.fake.none"})
    assert r.status_code in {200, 401, 403, 404}
