from __future__ import annotations

from argus_ai_assistant import respond_about_player
from argus_ai_oracle import evaluate


def test_oracle_to_assistant_flow():
    d = evaluate({"violations": [{"check_name": "reach", "level": "MID", "age_seconds": 5}]})
    msg = respond_about_player("Mateo", d.action, d.score, d.confidence)
    assert isinstance(msg, str) and len(msg) > 0
