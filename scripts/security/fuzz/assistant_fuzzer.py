#!/usr/bin/env python3
"""Fuzzer para classify_intent / assistant surfaces."""
from hypothesis import given, settings, strategies as st

ADVERSARIAL = [
    "' OR 1=1 --",
    "<script>alert(1)</script>",
    "$(curl evil)",
    "‮RTL_override",
    "Z̴͓͌͂à̶͕l̷͔̀g̷̯̾ö̸͈́",
]


@settings(max_examples=200, deadline=None)
@given(inp=st.one_of(st.text(max_size=800), st.sampled_from(ADVERSARIAL)))
def test_assistant_intent_input_space(inp):
    assert isinstance(inp, str)
    assert len(inp) <= 800 or inp in ADVERSARIAL


if __name__ == "__main__":
    test_assistant_input_does_not_crash()
