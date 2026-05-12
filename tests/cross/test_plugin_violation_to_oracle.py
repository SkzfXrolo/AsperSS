from __future__ import annotations

from argus_ai_oracle import evaluate


def test_plugin_violation_to_oracle_mock_http():
    plugin_payload = {"violations": [{"check_name": "speed_a", "level": "LOW", "age_seconds": 3}]}
    d = evaluate(plugin_payload)
    assert 0 <= d.score <= 1
