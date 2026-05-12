from __future__ import annotations

import math

from hypothesis import given, strategies as st

from argus_ai_features import FEATURE_NAMES, extract_features


@given(st.dictionaries(st.text(min_size=1, max_size=20), st.one_of(st.integers(), st.floats(allow_nan=True, allow_infinity=True), st.text()), max_size=20))
def test_features_invariants_deep(payload):
    fv = extract_features(payload)
    assert len(fv) == len(FEATURE_NAMES)
    for x in fv:
        assert isinstance(x, (int, float))
        assert not math.isnan(float(x)) if isinstance(x, float) else True
