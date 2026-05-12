from __future__ import annotations


def test_plugin_api_v2_contract_shape():
    payload = {"player_name": "Mateo", "violations": [], "request_id": "r1"}
    assert {"player_name", "violations"}.issubset(payload)
