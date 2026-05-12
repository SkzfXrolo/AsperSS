from __future__ import annotations

import math

from hypothesis import given, strategies as st

from argus_ai_features import FEATURE_NAMES, extract_features


@given(st.dictionaries(st.text(min_size=1, max_size=20), st.one_of(st.integers(), st.floats(allow_nan=False, allow_infinity=False), st.text(max_size=10), st.booleans(), st.none()), max_size=50))
def test_features_invariants(data):
    data.setdefault("violations", [])
    try:
        fv = extract_features(data)
    except ValueError:
        return
    assert len(fv) == len(FEATURE_NAMES)
    assert all(isinstance(x, (int, float)) for x in fv)
    assert all(math.isfinite(x) or math.isnan(x) for x in fv)
