from __future__ import annotations

import random

from argus_ai_oracle import evaluate


def _cases():
    return [
        {"name": "empty", "evidence": {"violations": []}},
        {"name": "low_reach", "evidence": {"violations": [{"check_name": "reach", "level": "LOW", "age_seconds": 5}]}},
        {"name": "mid_combo", "evidence": {"violations": [{"check_name": "reach", "level": "MID", "age_seconds": 10}, {"check_name": "speed", "level": "MID", "age_seconds": 9}]}},
        {"name": "critical_wall", "evidence": {"violations": [{"check_name": "hit_through_wall", "level": "CRITICAL", "age_seconds": 2}]}},
        {"name": "packet_fallback", "evidence": {"violations": [{"check_name": "reach_packet", "level": "HIGH", "age_seconds": 2}]}},
        {"name": "old_account", "evidence": {"violations": [{"check_name": "autoclicker", "level": "HIGH", "age_seconds": 2}], "playtime_hours": 250}},
        {"name": "new_account", "evidence": {"violations": [{"check_name": "autoclicker", "level": "HIGH", "age_seconds": 2}], "account_age_hours": 2}},
        {"name": "positive_scan", "evidence": {"violations": [{"check_name": "reach", "level": "MID", "age_seconds": 2}], "scan_detected_hacks_recent": True}},
        {"name": "reports", "evidence": {"violations": [{"check_name": "reach", "level": "MID", "age_seconds": 2}], "reports_in_chat": 10}},
        {"name": "prior_clean", "evidence": {"violations": [{"check_name": "reach", "level": "HIGH", "age_seconds": 2}], "prior_clean_scans": 6}},
        {"name": "decay", "evidence": {"violations": [], "current_score": 0.9, "last_evaluated_at_age_seconds": 25 * 3600}},
        {"name": "critical_mix", "evidence": {"violations": [{"check_name": "killaura_no_swing", "level": "CRITICAL", "age_seconds": 2}, {"check_name": "reach", "level": "HIGH", "age_seconds": 4}]}},
        {"name": "chat_spam", "evidence": {"violations": [{"check_name": "chat_spam", "level": "CRITICAL", "age_seconds": 1}]}},
        {"name": "unknown_check", "evidence": {"violations": [{"check_name": "zzz", "level": "HIGH", "age_seconds": 1}]}},
        {"name": "first_seen", "evidence": {"violations": [{"check_name": "speed", "level": "MID", "age_seconds": 3}], "first_seen_now": True}},
        {"name": "high_density", "evidence": {"violations": [{"check_name": "reach", "level": "HIGH", "age_seconds": i} for i in range(10)]}},
        {"name": "mixed_levels", "evidence": {"violations": [{"check_name": "reach", "level": "LOW", "age_seconds": 1}, {"check_name": "reach", "level": "MID", "age_seconds": 1}, {"check_name": "reach", "level": "HIGH", "age_seconds": 1}]}},
        {"name": "kick_like", "evidence": {"violations": [{"check_name": "killaura_multi", "level": "MID", "age_seconds": 1} for _ in range(4)]}},
        {"name": "ban_like", "evidence": {"violations": [{"check_name": "hit_through_wall", "level": "CRITICAL", "age_seconds": 1} for _ in range(4)]}},
        {"name": "long_tail", "evidence": {"violations": [{"check_name": "fasteat", "level": "LOW", "age_seconds": 3000}]}}
    ]


def test_oracle_evaluate_snapshots(snapshot):
    random.seed(12345)
    outputs = []
    for case in _cases():
        d = evaluate(case["evidence"])
        outputs.append(
            {
                "name": case["name"],
                "action": d.action,
                "confidence": d.confidence,
                "score": d.score,
                "top_factor": d.top_factor,
                "reasoning": d.reasoning,
            }
        )
    assert outputs == snapshot
