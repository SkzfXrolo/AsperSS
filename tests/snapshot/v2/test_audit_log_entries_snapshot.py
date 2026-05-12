from __future__ import annotations

import pytest


def test_audit_log_entries_snapshot(client, snapshot):
    r = client.get("/api/audit/logs")
    if r.status_code == 404:
        pytest.skip("Audit logs endpoint pendiente")
    assert {"status": r.status_code, "body": r.get_data(as_text=True)[:200]} == snapshot
