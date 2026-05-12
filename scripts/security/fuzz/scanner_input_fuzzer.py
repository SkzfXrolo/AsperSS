#!/usr/bin/env python3
"""
Fuzzer for scanner upload payload shape and sizes.
"""
from hypothesis import given, settings, strategies as st


json_scalar = st.one_of(st.none(), st.booleans(), st.integers(), st.floats(allow_nan=False), st.text(max_size=200))
json_value = st.recursive(
    json_scalar,
    lambda children: st.one_of(
        st.lists(children, max_size=10),
        st.dictionaries(st.text(max_size=30), children, max_size=10),
    ),
    max_leaves=50,
)


@settings(max_examples=150, deadline=None)
@given(payload=json_value)
def test_scanner_payload_shape(payload):
    # Invariante base: payload serializable sin caer.
    import json
    dumped = json.dumps(payload, ensure_ascii=False)
    assert isinstance(dumped, str)


if __name__ == "__main__":
    test_scanner_payload_shape()
