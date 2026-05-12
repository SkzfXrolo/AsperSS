from __future__ import annotations

import pytest


def test_brute_force_lockout_smoke(client):
    last = None
    for _ in range(20):
        last = client.post("/api/auth/login", json={"username": "x", "password": "bad"})
    assert last is not None
    assert last.status_code in {401, 429, 403}
