from __future__ import annotations

import time

import pytest

from argus_ai_oracle import evaluate


@pytest.mark.perf
def test_oracle_under_load_smoke():
    start = time.perf_counter()
    for _ in range(500):
        evaluate({"violations": [{"check_name": "speed_a", "level": "LOW", "age_seconds": 2}]})
    elapsed = time.perf_counter() - start
    assert elapsed < 2.0
