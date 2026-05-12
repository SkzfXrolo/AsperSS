from __future__ import annotations

from argus_ai_labeler import AutoLabel, combine_labels, confidence_threshold_for_training


def test_combine_labels_disagreement_branch():
    a = AutoLabel(1, "u", "p", 1.0, 0.9, "s1", "r1")
    b = AutoLabel(1, "u", "p", 0.0, 0.9, "s2", "r2")
    out = combine_labels([a, b])
    assert 1 in out
    assert out[1].source == "combined"


def test_threshold_known_sources():
    assert confidence_threshold_for_training("manual_ban") >= 0.5
    assert confidence_threshold_for_training("combined") == 0.4
