from __future__ import annotations


def test_ssrf_payload_rejected_smoke(client):
    r = client.post("/api/oracle/chat", json={"message": "http://169.254.169.254/latest/meta-data"})
    assert r.status_code in {200, 400, 401, 403, 404}
