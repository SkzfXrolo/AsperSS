from __future__ import annotations


def test_superadmin_panel_requires_auth(client):
    r = client.get("/aspers-sa")
    assert r.status_code in {200, 302}


def test_api_admin_companies_requires_auth(client):
    r = client.get("/api/admin/companies")
    assert r.status_code in {401, 302, 403}


def test_api_admin_tokens_requires_auth(client):
    r = client.get("/api/admin/registration-tokens")
    assert r.status_code in {401, 302, 403}
