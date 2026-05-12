from __future__ import annotations

import time
from contextlib import contextmanager

import pytest
import web_app.app as appmod


class _FlakyCursor:
    n = 0

    def execute(self, *args, **kwargs):
        self.n += 1
        if self.n % 2 == 0:
            raise RuntimeError("partial db failure")
        time.sleep(0.02)

    def fetchone(self):
        return {"ok": True}


@pytest.mark.chaos
def test_partial_db_failure(client, monkeypatch):
    @contextmanager
    def flaky():
        yield _FlakyCursor()

    monkeypatch.setattr(appmod, "get_api_db_cursor", flaky, raising=False)
    r = client.get("/health")
    assert r.status_code in {200, 500, 503}
