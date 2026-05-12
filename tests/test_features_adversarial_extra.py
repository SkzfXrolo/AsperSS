from __future__ import annotations

from argus_ai_features import FEATURE_NAMES, extract_features


def test_features_with_unicode_and_long_strings():
    payload = {
        "player_name": "玩家" * 200,
        "notes": "áéíóúñ" * 300,
        "violations": [{"check_name": "reach", "level": "LOW", "age_seconds": 1}],
    }
    fv = extract_features(payload)
    assert len(fv) == len(FEATURE_NAMES)


def test_features_with_mixed_adversarial_types():
    payload = {"violations": "not-a-list", "reports_in_chat": "999999999999", "scan_count_total": -1}
    fv = extract_features(payload)
    assert len(fv) == len(FEATURE_NAMES)
