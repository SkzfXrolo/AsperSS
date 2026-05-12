from __future__ import annotations

from argus_ai_assistant import classify_intent
from argus_ai_features import extract_features
from argus_ai_oracle import evaluate


def test_full_pipeline_dryrun():
    ev = {"violations": [{"check_name": "reach", "level": "LOW", "age_seconds": 2}]}
    _fv = extract_features(ev)
    d = evaluate(ev)
    intent = classify_intent("que paso con mateo")
    assert d.action in {"none", "watch", "kick", "ban"}
    assert hasattr(intent, "name")
