from __future__ import annotations

from argus_ai_oracle import evaluate


def test_oracle_score_is_capped_at_one():
    d = evaluate(
        {
            "violations": [
                {"check_name": "killaura", "level": "CRITICAL", "age_seconds": 1},
                {"check_name": "autoclicker", "level": "CRITICAL", "age_seconds": 1},
            ]
        }
    )
    assert 0.0 <= d.score <= 1.0


def test_oracle_confidence_bounds_with_empty_data():
    d = evaluate({"violations": []})
    assert 0.0 <= d.confidence <= 1.0
