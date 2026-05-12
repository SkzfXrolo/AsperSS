from __future__ import annotations

import pathlib


def test_openapi_consistency_v2():
    p = pathlib.Path("tests/contract/openapi.yaml")
    assert p.exists()
    t = p.read_text(encoding="utf-8")
    assert "/health" in t
