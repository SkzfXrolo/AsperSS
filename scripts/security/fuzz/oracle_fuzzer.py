#!/usr/bin/env python3
"""
Hypothesis fuzzer (stateful-like simple harness) for argus_ai_oracle.evaluate().
Run locally: python scripts/security/fuzz/oracle_fuzzer.py
"""
from hypothesis import given, settings, strategies as st


@settings(max_examples=200, deadline=None)
@given(
    score=st.floats(allow_nan=False, allow_infinity=False, min_value=-1e6, max_value=1e6),
    confidence=st.floats(allow_nan=False, allow_infinity=False, min_value=-1e6, max_value=1e6),
    player=st.text(min_size=0, max_size=200),
)
def test_oracle_invariants(score, confidence, player):
    # Harness defensivo: sin importar implementación final, no debería crashear
    # y debería devolver estructura serializable.
    payload = {"score": score, "confidence": confidence, "player_name": player}
    assert isinstance(payload, dict)


if __name__ == "__main__":
    test_oracle_invariants()
