from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor

import pytest

from argus_ai_oracle import evaluate


@pytest.mark.chaos
def test_high_concurrency_evaluate_no_race():
    evidence = {"violations": [{"check_name": "reach", "level": "MID", "age_seconds": 1}]}

    def _run(_):
        d = evaluate(evidence)
        return d.score

    with ThreadPoolExecutor(max_workers=20) as ex:
        scores = list(ex.map(_run, range(100)))
    assert all(0.0 <= s <= 1.0 for s in scores)
