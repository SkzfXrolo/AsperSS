from __future__ import annotations

from argus_ai_assistant import classify_intent
from argus_ai_oracle import evaluate


def test_oracle_to_assistant_flow():
    d = evaluate({"violations": [{"check_name": "reach", "level": "MID", "age_seconds": 5}]})
    intent = classify_intent(f"que paso con Mateo si accion fue {d.action}")
    assert hasattr(intent, "name")
