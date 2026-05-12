from __future__ import annotations

import json
import time
from pathlib import Path

import pytest

from argus_ai_oracle import evaluate


@pytest.mark.perf
def test_oracle_regression_against_baseline():
    baseline_path = Path("tests/perf/baselines/oracle_v1.0.json")
    baseline = json.loads(baseline_path.read_text(encoding="utf-8"))["metrics"]

    timings = []
    ev = {"violations": [{"check_name": "reach", "level": "MID", "age_seconds": 1}]}
    for _ in range(500):
        t0 = time.perf_counter()
        evaluate(ev)
        timings.append((time.perf_counter() - t0) * 1000)
    timings.sort()
    p50 = timings[int(0.50 * (len(timings) - 1))]
    p95 = timings[int(0.95 * (len(timings) - 1))]
    p99 = timings[int(0.99 * (len(timings) - 1))]

    assert p50 <= baseline["p50_ms"] * 1.2
    assert p95 <= baseline["p95_ms"] * 1.2
    assert p99 <= baseline["p99_ms"] * 1.2
