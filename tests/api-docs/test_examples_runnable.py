from __future__ import annotations

import json


def test_example_payload_is_json_runnable():
    payload = '{"violations":[{"check":"speed","vl":1.0}]}'
    parsed = json.loads(payload)
    assert "violations" in parsed
