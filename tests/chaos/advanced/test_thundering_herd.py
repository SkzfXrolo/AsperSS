from __future__ import annotations

import concurrent.futures

import pytest


@pytest.mark.chaos
def test_thundering_herd_smoke(client):
    def hit():
        return client.get("/health").status_code

    with concurrent.futures.ThreadPoolExecutor(max_workers=20) as ex:
        out = list(ex.map(lambda _: hit(), range(50)))
    assert all(c in {200, 503} for c in out)
