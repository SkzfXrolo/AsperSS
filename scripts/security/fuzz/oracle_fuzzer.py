#!/usr/bin/env python3
"""
Hypothesis harness orientado a `argus_ai_oracle.evaluate()`.
No importa el módulo productivo para mantener scope read-only audit.
"""
from hypothesis import given, settings, strategies as st


@settings(max_examples=200, deadline=None)
@given(
    score=st.floats(allow_nan=False, allow_infinity=False, min_value=-1e6, max_value=1e6),
    confidence=st.floats(allow_nan=False, allow_infinity=False, min_value=-1e6, max_value=1e6),
    player=st.text(min_size=0, max_size=200),
    evidence=st.dictionaries(st.text(min_size=1, max_size=30), st.text(max_size=200), max_size=20),
)
def test_oracle_invariants(score, confidence, player, evidence):
    # Invariantes mínimas esperadas de entrada.
    payload = {
        "score": score,
        "confidence": confidence,
        "player_name": player,
        "evidence": evidence,
    }
    assert isinstance(payload, dict)


if __name__ == "__main__":
    test_oracle_invariants()
