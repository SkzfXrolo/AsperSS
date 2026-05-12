from __future__ import annotations

from contextlib import contextmanager

import pytest
import web_app.app as appmod


@pytest.mark.chaos
def test_health_when_db_unavailable(client, monkeypatch):
    @contextmanager
    def broken_cursor():
        raise RuntimeError("db unavailable")
        yield

    monkeypatch.setattr(appmod, "get_api_db_cursor", broken_cursor, raising=False)
    r = client.get("/api/db-status")
    assert r.status_code in {302, 503, 500}
