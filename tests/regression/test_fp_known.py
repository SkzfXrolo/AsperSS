from __future__ import annotations

from argus_ai_oracle import evaluate


def test_known_false_positive_jump_fly():
    d = evaluate({"violations": [{"check_name": "fly", "level": "LOW", "age_seconds": 1}]})
    assert d.action in {"none", "watch"}


def test_known_false_positive_scaffold_normal_build():
    d = evaluate({"violations": [{"check_name": "scaffold", "level": "LOW", "age_seconds": 1}]})
    assert d.action in {"none", "watch"}
