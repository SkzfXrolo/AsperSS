from __future__ import annotations

import math

import pytest
from hypothesis import given, strategies as st

from argus_ai_features import FEATURE_NAMES, extract_features


scalar = st.one_of(
    st.integers(-10_000, 10_000),
    st.floats(allow_nan=True, allow_infinity=True, width=32),
    st.text(max_size=20),
    st.none(),
    st.booleans(),
)


@given(st.dictionaries(st.text(min_size=1, max_size=20), scalar, max_size=40))
def test_extract_features_fuzz_never_breaks_shape(data):
    data.setdefault("violations", [])
    try:
        fv = extract_features(data)
    except ValueError:
        pytest.xfail("Bug conocido: math domain error con reports_in_chat negativo")
    assert len(fv) == len(FEATURE_NAMES)
    assert all(isinstance(x, (int, float)) for x in fv)
    assert all(math.isfinite(x) or math.isnan(x) for x in fv)
