from __future__ import annotations

import time

import pytest

from argus_ai_features import extract_features


@pytest.mark.perf
def test_features_throughput_1000_under_2s(sample_evidence):
    t0 = time.perf_counter()
    for _ in range(1000):
        extract_features(sample_evidence)
    elapsed = time.perf_counter() - t0
    assert elapsed < 2.0
