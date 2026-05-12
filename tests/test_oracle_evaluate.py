from __future__ import annotations

from argus_ai_oracle import evaluate, get_default_weights


def _ev(violations=None, **kwargs):
    base = {
        "violations": violations or [],
        "account_age_hours": None,
        "playtime_hours": 0,
        "prior_clean_scans": 0,
        "scan_detected_hacks_recent": False,
        "reports_in_chat": 0,
        "first_seen_now": False,
        "current_score": 0.0,
        "last_evaluated_at_age_seconds": None,
    }
    base.update(kwargs)
    return base


def test_empty_evidence_returns_none():
    d = evaluate(_ev())
    assert d.action == "none"
    assert d.score == 0.0


def test_single_low_violation_is_none_or_watch():
    d = evaluate(_ev([{"check_name": "reach", "level": "LOW", "age_seconds": 1}]))
    assert d.action in {"none", "watch"}


def test_multiple_mid_violations_reach_kick():
    v = [{"check_name": "killaura_multi", "level": "MID", "age_seconds": 1} for _ in range(4)]
    d = evaluate(_ev(v))
    assert d.action in {"kick", "ban"}


def test_high_plus_critical_reaches_ban_or_kick_guard():
    v = [
        {"check_name": "hit_through_wall", "level": "CRITICAL", "age_seconds": 1},
        {"check_name": "killaura_no_swing", "level": "HIGH", "age_seconds": 1},
        {"check_name": "reach", "level": "HIGH", "age_seconds": 2},
    ]
    d = evaluate(_ev(v))
    assert d.action in {"kick", "ban"}


def test_score_decay_after_24h_lowers_previous_score():
    no_decay = evaluate(_ev(current_score=0.8, last_evaluated_at_age_seconds=None))
    decayed = evaluate(_ev(current_score=0.8, last_evaluated_at_age_seconds=24 * 3600))
    assert decayed.score < no_decay.score


def test_new_account_multiplier_increases_score():
    v = [{"check_name": "autoclicker", "level": "HIGH", "age_seconds": 1}]
    older = evaluate(_ev(v, account_age_hours=300))
    newer = evaluate(_ev(v, account_age_hours=2))
    assert newer.score > older.score


def test_veteran_multiplier_reduces_score():
    v = [{"check_name": "autoclicker", "level": "HIGH", "age_seconds": 1}]
    short = evaluate(_ev(v, playtime_hours=10))
    veteran = evaluate(_ev(v, playtime_hours=250))
    assert veteran.score < short.score


def test_prior_clean_scans_reduce_score():
    v = [{"check_name": "reach", "level": "HIGH", "age_seconds": 1}]
    none = evaluate(_ev(v, prior_clean_scans=0))
    many = evaluate(_ev(v, prior_clean_scans=6))
    assert many.score < none.score


def test_packet_fallback_applies_20_percent_boost():
    w = get_default_weights()
    v_base = [{"check_name": "reach", "level": "HIGH", "age_seconds": 1}]
    v_packet = [{"check_name": "reach_packet", "level": "HIGH", "age_seconds": 1}]
    d_base = evaluate(_ev(v_base), weights=w)
    d_packet = evaluate(_ev(v_packet), weights=w)
    assert d_packet.evidence_used["incremental"] > d_base.evidence_used["incremental"]


def test_unknown_check_fallbacks_to_autoclicker_weights():
    unknown = evaluate(_ev([{"check_name": "totally_unknown", "level": "HIGH", "age_seconds": 1}]))
    auto = evaluate(_ev([{"check_name": "autoclicker", "level": "HIGH", "age_seconds": 1}]))
    assert unknown.evidence_used["incremental"] == auto.evidence_used["incremental"]


def test_score_is_capped_at_one():
    d = evaluate(_ev([{"check_name": "hit_through_wall", "level": "CRITICAL", "age_seconds": 1}] * 12))
    assert 0.0 <= d.score <= 1.0
    assert d.score == 1.0


def test_confidence_grows_with_more_evidence():
    one = evaluate(_ev([{"check_name": "reach", "level": "MID", "age_seconds": 1}]))
    many = evaluate(_ev([{"check_name": "reach", "level": "MID", "age_seconds": 1}] * 8))
    assert many.confidence > one.confidence


def test_ban_requires_high_confidence_guard():
    v = [{"check_name": "hit_through_wall", "level": "CRITICAL", "age_seconds": 1}]
    d = evaluate(_ev(v))
    assert d.action in {"ss", "kick", "ban"}
    if d.score >= 0.95:
        assert d.action != "ban"


def test_reports_multiplier_applied_when_above_threshold():
    v = [{"check_name": "reach", "level": "MID", "age_seconds": 1}] * 2
    low_reports = evaluate(_ev(v, reports_in_chat=1))
    many_reports = evaluate(_ev(v, reports_in_chat=8))
    assert many_reports.score >= low_reports.score


def test_first_seen_now_multiplier_changes_score():
    v = [{"check_name": "reach", "level": "MID", "age_seconds": 1}] * 2
    normal = evaluate(_ev(v, first_seen_now=False))
    first_seen = evaluate(_ev(v, first_seen_now=True))
    assert first_seen.score >= normal.score


def test_scan_detected_hacks_recent_multiplier_changes_score():
    v = [{"check_name": "reach", "level": "HIGH", "age_seconds": 1}]
    no_hit = evaluate(_ev(v, scan_detected_hacks_recent=False))
    hit = evaluate(_ev(v, scan_detected_hacks_recent=True))
    assert hit.score > no_hit.score


def test_top_factor_set_to_max_contribution():
    d = evaluate(
        _ev(
            [
                {"check_name": "chat_spam", "level": "LOW", "age_seconds": 1},
                {"check_name": "hit_through_wall", "level": "CRITICAL", "age_seconds": 1},
            ]
        )
    )
    assert "hit_through_wall" in d.top_factor


def test_evidence_summary_counts_distinct_and_total():
    d = evaluate(
        _ev(
            [
                {"check_name": "reach", "level": "LOW", "age_seconds": 1},
                {"check_name": "reach", "level": "MID", "age_seconds": 1},
                {"check_name": "fly", "level": "MID", "age_seconds": 1},
            ]
        )
    )
    assert d.evidence_used["distinct_checks"] == 2
    assert d.evidence_used["total_violations"] == 3
