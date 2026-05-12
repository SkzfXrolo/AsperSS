from __future__ import annotations


def test_scanner_payload_min_contract():
    payload = {"token": "abc", "machine_id": "m1", "machine_name": "PC-1"}
    required = {"token", "machine_id", "machine_name"}
    assert required.issubset(payload.keys())
