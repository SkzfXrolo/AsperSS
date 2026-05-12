from __future__ import annotations

from argus_ai_features import FEATURE_NAMES, extract_features


def test_features_snapshots(snapshot):
    cases = [
        {},
        {"violations": [{"check_name": "reach", "level": "LOW", "age_seconds": 1}]},
        {"violations": [{"check_name": "killaura_no_swing", "level": "HIGH", "age_seconds": 4}], "reports_in_chat": 5},
        {"violations": [{"check_name": "autoclicker", "level": "CRITICAL", "age_seconds": 2}], "scan_detected_hacks_recent": True},
    ]
    out = []
    for c in cases:
        fv = extract_features(c)
        out.append({"len": len(fv), "head": fv[:10], "tail": fv[-5:], "n_names": len(FEATURE_NAMES)})
    assert out == snapshot
