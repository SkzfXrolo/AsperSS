from __future__ import annotations

import pytest


@pytest.mark.chaos
def test_partition_tolerance_placeholder(client, monkeypatch):
    monkeypatch.setenv("ARGUS_NETWORK_PARTITION", "1")
    r = client.get("/health")
    assert r.status_code in {200, 503}
