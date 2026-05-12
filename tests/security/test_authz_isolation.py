from __future__ import annotations

from contextlib import contextmanager

import web_app.app as appmod


class _FakeCursor:
    def execute(self, *args, **kwargs):
        return None

    def fetchone(self):
        # decision pertenece a otra company
        return {"company_id": 999, "player_uuid": "u2", "player_name": "Other"}


@contextmanager
def _fake_db_cursor():
    yield _FakeCursor()


def test_feedback_blocks_cross_company_access(client, monkeypatch):
    with client.session_transaction() as sess:
        sess["user_id"] = 10
        sess["company_id"] = 1
        sess["roles"] = ["staff"]
    monkeypatch.setattr(appmod, "get_user_by_id", lambda *_: {"id": 10, "company_id": 1, "is_super_admin": False, "username": "u"})
    monkeypatch.setattr(appmod, "get_api_db_cursor", _fake_db_cursor)
    monkeypatch.setattr(appmod, "_plugin_schema_guard", lambda: None)

    r = client.post("/api/ai/feedback", json={"decision_id": 55, "label": 1})
    assert r.status_code in {400, 403}
