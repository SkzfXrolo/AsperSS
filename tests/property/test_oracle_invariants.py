from __future__ import annotations

from hypothesis import given, strategies as st

from argus_ai_oracle import evaluate


levels = st.sampled_from(["LOW", "MID", "HIGH", "CRITICAL", "weird"])
checks = st.sampled_from(["reach", "autoclicker", "killaura_no_swing", "speed", "unknown_x"])


@given(
    violations=st.lists(
        st.fixed_dictionaries(
            {
                "check_name": checks,
                "level": levels,
                "age_seconds": st.floats(min_value=0, max_value=10_000, allow_nan=False, allow_infinity=False),
            }
        ),
        max_size=20,
    ),
    current_score=st.floats(min_value=0, max_value=2, allow_nan=False, allow_infinity=False),
)
def test_oracle_score_in_unit_interval(violations, current_score):
    d = evaluate({"violations": violations, "current_score": current_score})
    assert 0.0 <= d.score <= 1.0
    assert 0.0 <= d.confidence <= 1.0


@given(
    violations=st.lists(
        st.fixed_dictionaries(
            {
                "check_name": checks,
                "level": levels,
                "age_seconds": st.floats(min_value=0, max_value=10_000, allow_nan=False, allow_infinity=False),
            }
        ),
        max_size=15,
    )
)
def test_oracle_deterministic_core_output(violations):
    ev = {"violations": violations, "current_score": 0.2, "reports_in_chat": 1}
    a = evaluate(ev)
    b = evaluate(ev)
    assert a.score == b.score
    assert a.confidence == b.confidence
    assert a.action == b.action
