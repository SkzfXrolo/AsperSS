from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor

import pytest


@pytest.mark.chaos
def test_cache_miss_storm(client):
    def hit(i: int):
        return client.get(f"/api/scans?offset={i}&limit=1").status_code

    with ThreadPoolExecutor(max_workers=20) as ex:
        codes = list(ex.map(hit, range(60)))
    assert all(c in {200, 302, 401, 500} for c in codes)
