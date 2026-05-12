from __future__ import annotations

import pytest

from argus_ai_assistant import classify_intent


@pytest.mark.parametrize(
    "text",
    [
        "holaa",
        "k onda con mateo",
        "xq kick a pedro",
        "cuantos bns hoy",
        "help pls bro",
        "que onda mateo status now",
    ],
)
def test_intent_classifier_handles_typos_and_mixed_lang(text):
    intent = classify_intent(text)
    assert isinstance(intent, str)
    assert len(intent) > 0
