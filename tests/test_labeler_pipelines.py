from __future__ import annotations

from argus_ai_labeler import (
    AutoLabel,
    label_from_age_stats_mismatch,
    label_from_clean_history,
    label_from_cross_server_history,
    label_from_hit_accept_rate,
    label_from_knn_propagation,
    label_from_manual_bans,
    label_from_player_reports,
    label_from_scanner_results,
    label_from_ss_outcomes,
    label_from_unbans,
    label_from_violation_clusters,
    label_from_yaw_consistency,
)
from argus_ai_trainer import KNNCheaterClassifier, KNNExample


def _decision(**kwargs):
    base = {"id": 1, "player_uuid": "u1", "player_name": "Mateo", "created_at": 1000, "action": "kick"}
    base.update(kwargs)
    return base


def _assert_labels(labels):
    assert isinstance(labels, list)
    assert all(isinstance(l, AutoLabel) for l in labels)
    assert all(isinstance(l.reasoning, str) and l.reasoning.strip() for l in labels)


def test_pipeline_ss_outcomes():
    labels = label_from_ss_outcomes([_decision()], {"u1": {"detected_hacks": True, "scan_at": 2000}})
    _assert_labels(labels)


def test_pipeline_manual_bans():
    labels = label_from_manual_bans([_decision()], [{"player_uuid": "u1", "banned_at": 2000, "reason": "cheat"}])
    _assert_labels(labels)


def test_pipeline_unbans():
    labels = label_from_unbans([_decision(action="ban")], [{"player_uuid": "u1", "reason": "false positive"}])
    _assert_labels(labels)


def test_pipeline_clean_history():
    labels = label_from_clean_history(
        [_decision()],
        {"u1": {"last_seen_at": 1000 + 9 * 86400, "last_violation_at": 10}},
    )
    _assert_labels(labels)


def test_pipeline_player_reports():
    reps = [{"reporter_uuid": f"r{i}", "reported_at": 1100} for i in range(4)]
    labels = label_from_player_reports([_decision()], {"u1": reps})
    _assert_labels(labels)


def test_pipeline_violation_clusters():
    labels = label_from_violation_clusters(
        [_decision(evidence_summary={"v_criticals": 2, "v_highs": 3, "distinct_checks": 3, "cluster_density": 0.8})]
    )
    _assert_labels(labels)


def test_pipeline_knn_propagation():
    knn = KNNCheaterClassifier(["x", "y"], k=3, min_examples=3)
    knn.add_example(KNNExample("a", "A", [1, 1], 1.0))
    knn.add_example(KNNExample("b", "B", [1, 1], 1.0))
    knn.add_example(KNNExample("c", "C", [1, 1], 1.0))
    knn.add_example(KNNExample("d", "D", [1, 1], 1.0))
    knn.add_example(KNNExample("e", "E", [1, 1], 1.0))
    labels = label_from_knn_propagation([_decision(feature_vector=[1, 1])], knn)
    _assert_labels(labels)


def test_pipeline_yaw_consistency():
    labels = label_from_yaw_consistency([_decision(evidence_summary={"yaw_stability_extreme": True})])
    _assert_labels(labels)


def test_pipeline_age_stats_mismatch():
    labels = label_from_age_stats_mismatch(
        [_decision(evidence_summary={"account_age_hours": 5, "avg_cps": 16, "avg_reach": 4.5})]
    )
    _assert_labels(labels)


def test_pipeline_hit_accept_rate():
    labels = label_from_hit_accept_rate([_decision(evidence_summary={"hit_accept_rate": 0.995, "total_hits": 60})])
    _assert_labels(labels)


def test_pipeline_scanner_results():
    labels = label_from_scanner_results(
        [_decision()],
        {"u1": {"detected_processes": ["vape"], "detected_files": [], "severity": "HIGH"}},
    )
    _assert_labels(labels)


def test_pipeline_cross_server_history():
    labels = label_from_cross_server_history([_decision()], {"u1": {"banned_in_servers": ["a", "b"]}})
    _assert_labels(labels)
