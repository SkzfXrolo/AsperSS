from __future__ import annotations

import pytest


@pytest.mark.parametrize(
    "payload",
    [
        "' OR 1=1 --",
        "\" OR \"1\"=\"1",
        "'; DROP TABLE scans; --",
        "admin'/*",
    ],
)
def test_scan_filters_resist_sqli_payloads(client, payload):
    r = client.get(f"/api/scans?search={payload}")
    # sin auth debe bloquear, pero nunca reventar con 500 por payload
    assert r.status_code in {401, 302, 400}
