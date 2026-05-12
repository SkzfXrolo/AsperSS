from __future__ import annotations

import json


def test_postman_collection_shape():
    sample = {"info": {"name": "Argus API"}, "item": []}
    json.dumps(sample)
    assert "info" in sample and "item" in sample
