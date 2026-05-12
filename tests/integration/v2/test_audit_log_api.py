from __future__ import annotations

import pytest


def test_audit_log_api_placeholder(client):
    r = client.get("/api/audit/logs")
    if r.status_code == 404:
        pytest.skip("Audit log API v2 pendiente de D")
    assert r.status_code in {200, 401, 403}
