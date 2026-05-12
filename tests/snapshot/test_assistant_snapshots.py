from __future__ import annotations

import random

import argus_ai_assistant as A


def _ctx(player="Mateo", action="watch", score=0.62):
    return {
        "player_name": player,
        "score": score,
        "confidence": 0.72,
        "last_action": action,
        "top_factor": "reach HIGH",
        "top_check": "reach",
        "violations_total": 5,
        "distinct_checks": 2,
        "clean_scans": 1,
        "evaluations_count": 6,
        "playtime_hours": 20,
    }


def test_assistant_intent_and_response_snapshots(snapshot):
    random.seed(12345)
    inputs = [
        "hola", "buenas", "ayuda", "help", "resumen del dia",
        "reporte de la semana", "top sospechosos", "historial de Mateo",
        "que hago con Mateo", "compara Mateo vs Juan", "@Mateo", "Mateo",
        "por que kickeaste a Pedro", "estado de X", "dime Neo", "unknown intent",
        "se parece Neo a Zion", "que puedes hacer", "como esta Mateo",
        "que tal va Mateo", "historia de Neo", "antecedentes Zion",
        "por que baneaste a X", "resumen", "brief de la semana",
        "cheaters mas claros", "opciones", "comandos", "saludos", "hi",
    ]
    out = []
    for text in inputs:
        intent = A.classify_intent(text)
        answer = A.respond_about_player(_ctx(), intent=intent.name if intent.name != "unknown" else "status", rng=random.Random(7))
        out.append({"text": text, "intent": intent.name, "slots": intent.slots, "answer": answer})
    assert out == snapshot
