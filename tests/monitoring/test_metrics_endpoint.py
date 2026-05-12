from __future__ import annotations


def test_metrics_endpoint_format(client):
    r = client.get("/metrics")
    assert r.status_code in {200, 404}
    if r.status_code == 200:
        body = r.get_data(as_text=True)
        assert "# HELP" in body or "# TYPE" in body
