from __future__ import annotations

from hypothesis import given, strategies as st

from argus_ai_oracle import evaluate


@given(st.lists(st.fixed_dictionaries({"check_name": st.text(min_size=1, max_size=20), "level": st.sampled_from(["LOW", "MID", "HIGH", "CRITICAL"]), "age_seconds": st.integers(min_value=0, max_value=100000)}), max_size=40))
def test_oracle_basic_invariants(violations):
    d = evaluate({"violations": violations})
    assert 0 <= d.score <= 1
    assert 0 <= d.confidence <= 1
    assert d.action in {"none", "watch", "ss", "kick", "ban"}


@given(st.integers(min_value=0, max_value=10))
def test_oracle_monotonicity_soft(n):
    base = evaluate({"violations": []})
    more = evaluate({"violations": [{"check_name": "reach", "level": "MID", "age_seconds": 1} for _ in range(n)]})
    assert more.score >= base.score
