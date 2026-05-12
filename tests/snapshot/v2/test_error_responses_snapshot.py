from __future__ import annotations


def test_error_response_snapshot(client, snapshot):
    r = client.get("/route-that-should-not-exist")
    assert {"status": r.status_code, "body": r.get_data(as_text=True)[:120]} == snapshot
