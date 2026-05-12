from __future__ import annotations

import random

from argus_ai_assistant import daily_brief, generate_warning, respond_about_player


def _player_ctx(**kwargs):
    base = {
        "player_name": "Mateo",
        "score": 0.62,
        "confidence": 0.72,
        "last_action": "watch",
        "top_factor": "reach HIGH",
        "top_check": "reach",
        "violations_total": 5,
        "distinct_checks": 2,
        "clean_scans": 1,
        "evaluations_count": 6,
        "playtime_hours": 20,
    }
    base.update(kwargs)
    return base


def test_respond_about_player_status_contains_player_name():
    txt = respond_about_player(_player_ctx(), intent="status", rng=random.Random(1))
    assert "Mateo" in txt


def test_respond_about_player_history_works():
    txt = respond_about_player(_player_ctx(violations_total=12), intent="history", rng=random.Random(2))
    assert isinstance(txt, str) and txt.strip()


def test_respond_about_player_advice_works():
    txt = respond_about_player(_player_ctx(last_action="ss"), intent="advice", rng=random.Random(3))
    assert "Mateo" in txt


def test_daily_brief_busy_path():
    txt = daily_brief(
        {
            "date": "2026-05-12",
            "evaluations_count": 40,
            "bans_count": 2,
            "kicks_count": 5,
            "ss_count": 8,
            "top_player": {"player_name": "Neo", "score": 0.92, "top_check": "killaura_no_swing"},
            "ml_samples": 120,
            "ml_accuracy": 0.88,
            "pending_count": 3,
        },
        rng=random.Random(4),
    )
    assert "Neo" in txt
    assert "2026-05-12" in txt


def test_generate_warning_non_empty():
    txt = generate_warning(_player_ctx(), rng=random.Random(5))
    assert isinstance(txt, str) and txt.strip()
