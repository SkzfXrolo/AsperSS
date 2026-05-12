from __future__ import annotations

import pytest

from argus_ai_assistant import classify_intent


@pytest.mark.parametrize(
    "text,expected",
    [
        ("hola", "greeting"),
        ("que tal", "greeting"),
        ("buenas", "greeting"),
        ("como esta Mateo", "status"),
        ("que tal va Mateo", "status"),
        ("estado de X", "status"),
        ("por que kickeaste a Pedro", "explain_decision"),
        ("porque baneaste a X", "explain_decision"),
        ("resumen del dia", "daily_summary"),
        ("reporte de la semana", "weekly_summary"),
        ("ayuda", "help"),
        ("que puedes hacer", "help"),
        ("help", "help"),
        ("compara Mateo vs Juan", "compare"),
        ("se parece Mateo a Juan", "compare"),
        ("historial de Mateo", "history"),
        ("que hago con Mateo", "advice"),
        ("@Mateo", "status_short"),
        ("Mateo", "status_short"),
        ("top sospechosos", "top_suspects"),
        ("cheaters mas claros", "top_suspects"),
    ],
)
def test_classify_intent_cases(text, expected):
    assert classify_intent(text).name == expected


@pytest.mark.parametrize("text", ["", "???", "lorem ipsum dolor sit amet"])
def test_classify_intent_ambiguous_or_empty(text):
    out = classify_intent(text)
    assert out.name in {"unknown", "status_short"}
