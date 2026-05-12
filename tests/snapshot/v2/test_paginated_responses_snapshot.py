from __future__ import annotations

import pytest


def test_paginated_response_snapshot(client, snapshot):
    r = client.get("/api/scans?page=1&limit=5")
    if r.status_code == 302:
        pytest.skip("Requiere sesión")
    assert {"status": r.status_code, "body": r.get_data(as_text=True)[:200]} == snapshot
