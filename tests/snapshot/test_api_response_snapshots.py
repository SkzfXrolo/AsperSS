from __future__ import annotations


def test_api_response_snapshots(client, snapshot):
    responses = []
    for method, path in [("get", "/health"), ("get", "/api/version"), ("get", "/")]:
        r = getattr(client, method)(path)
        responses.append(
            {
                "path": path,
                "status": r.status_code,
                "content_type": r.headers.get("Content-Type", ""),
                "body_prefix": r.get_data(as_text=True)[:120],
            }
        )
    assert responses == snapshot
