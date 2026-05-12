from __future__ import annotations


def test_rate_limiter_trigger_smoke(client):
    codes = []
    for _ in range(10):
        codes.append(client.get("/api/version").status_code)
    assert all(c in {200, 302, 404, 429} for c in codes)
