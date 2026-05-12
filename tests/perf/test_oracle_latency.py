from __future__ import annotations

import time

import pytest

from argus_ai_oracle import evaluate
from argus_ai_trainer import generate_bootstrap_dataset


@pytest.mark.perf
def test_oracle_p95_latency_under_100ms():
    def _identity(ev):
        return ev

    X, _, _ = generate_bootstrap_dataset(_identity, n_cheaters=20, n_clean=20, n_borderline=10)
    timings_ms = []
    for ev in X:
        t0 = time.perf_counter()
        evaluate(ev)
        timings_ms.append((time.perf_counter() - t0) * 1000)
    timings_ms.sort()
    p95 = timings_ms[int(0.95 * (len(timings_ms) - 1))]
    assert p95 < 100.0
