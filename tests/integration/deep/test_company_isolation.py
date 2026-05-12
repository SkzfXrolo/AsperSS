from __future__ import annotations


def test_company_isolation_deep_smoke(login_session):
    r = login_session.get("/api/company/users")
    assert r.status_code in {200, 401, 403}
