from __future__ import annotations

import json


def test_structured_log_json_sample():
    sample = '{"level":"info","message":"ok","request_id":"r1"}'
    obj = json.loads(sample)
    assert {"level", "message", "request_id"}.issubset(obj.keys())
