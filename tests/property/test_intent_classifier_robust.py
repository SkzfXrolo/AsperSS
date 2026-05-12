from __future__ import annotations

from hypothesis import given, strategies as st

from argus_ai_assistant import classify_intent


@given(st.text())
def test_classify_intent_never_raises_for_arbitrary_text(s):
    out = classify_intent(s)
    assert isinstance(out.name, str)
    assert isinstance(out.slots, dict)
    assert 0.0 <= out.confidence <= 1.0
