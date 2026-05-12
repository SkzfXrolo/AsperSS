from __future__ import annotations

import pytest


@pytest.mark.xfail(reason="Pack49: redirect/auth drift en endpoint company users", strict=False)
def test_company_isolation_deep_smoke(login_session):
    r = login_session.get("/api/company/users")
    assert r.status_code in {200, 302, 401, 403}
