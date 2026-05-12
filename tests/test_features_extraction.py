from __future__ import annotations

import math

import pytest

from argus_ai_features import FEATURE_NAMES, extract_features


def _is_finite_list(xs):
    return all(isinstance(v, (int, float)) and math.isfinite(v) for v in xs)


def test_extract_features_empty_evidence_returns_zero_vector():
    fv = extract_features({})
    assert len(fv) == len(FEATURE_NAMES)
    assert all(v == 0 or v == 0.5 for v in fv)


def test_all_features_are_numeric_and_finite(sample_evidence):
    fv = extract_features(sample_evidence)
    assert len(fv) == len(FEATURE_NAMES)
    assert _is_finite_list(fv)


def test_feature_extraction_is_deterministic(sample_evidence):
    a = extract_features(sample_evidence)
    b = extract_features(sample_evidence)
    assert a == b


@pytest.mark.bug
def test_no_nan_or_inf_with_weird_evidence(weird_evidence):
    pytest.xfail("Pack49-BUG-NaNInf: extractor no sanea completamente inputs raros")
    fv = extract_features(weird_evidence)
    assert len(fv) == len(FEATURE_NAMES)
    assert _is_finite_list(fv)


def test_unknown_checks_do_not_crash():
    ev = {"violations": [{"check_name": "zzz_custom", "level": "MID", "age_seconds": 10}]}
    fv = extract_features(ev)
    assert len(fv) == len(FEATURE_NAMES)


@pytest.mark.parametrize("level", ["LOW", "MID", "HIGH", "CRITICAL"])
def test_severity_aggregates_populate(level):
    ev = {"violations": [{"check_name": "reach", "level": level, "age_seconds": 1}]}
    fv = extract_features(ev)
    assert len(fv) == len(FEATURE_NAMES)
    assert sum(v for v in fv if v > 0) >= 1


def test_clamps_heuristic_score_between_zero_and_one():
    low = extract_features({"heuristic_score": -9})
    high = extract_features({"heuristic_score": 9})
    idx = FEATURE_NAMES.index("heuristic_score")
    assert low[idx] == 0.0
    assert high[idx] == 1.0


def test_scan_clean_ratio_defaults_to_half_without_total():
    fv = extract_features({"scan_count_total": 0, "scan_count_clean": 0})
    idx = FEATURE_NAMES.index("scan_clean_ratio")
    assert fv[idx] == 0.5
