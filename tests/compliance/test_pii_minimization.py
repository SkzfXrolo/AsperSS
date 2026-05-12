from __future__ import annotations


def test_response_has_no_unnecessary_pii():
    payload = {"player": "Mateo", "score": 0.7}
    blocked = {"password", "dni", "credit_card", "token"}
    assert blocked.isdisjoint(payload.keys())
