from __future__ import annotations

import pytest

from argus_ai_oracle import evaluate_hybrid


@pytest.mark.chaos
def test_corrupt_model_falls_back_to_heuristic():
    evidence = {"violations": [{"check_name": "reach", "level": "MID", "age_seconds": 1}]}
    d = evaluate_hybrid(evidence, log_reg=object(), feature_vector=[0.1], sequence=["reach", "reach"])
    assert d.action in {"none", "watch", "ss", "kick", "ban"}
