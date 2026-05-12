from __future__ import annotations

import time
from contextlib import contextmanager

import pytest
import web_app.app as appmod


class _SlowCursor:
    def execute(self, *args, **kwargs):
        time.sleep(0.05)
        return None

    def fetchone(self):
        return {"ok": True}


@pytest.mark.chaos
def test_slow_db_does_not_crash_health(client, monkeypatch):
    @contextmanager
    def slow_cursor():
        yield _SlowCursor()

    monkeypatch.setattr(appmod, "get_api_db_cursor", slow_cursor, raising=False)
    r = client.get("/health")
    assert r.status_code in {200, 503}
