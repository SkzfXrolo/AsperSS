from __future__ import annotations

from argus_ai_features import extract_features
from argus_ai_trainer import (
    KNNCheaterClassifier,
    KNNExample,
    LogisticRegression,
    TemporalPatternDetector,
    ensemble_predict,
    generate_bootstrap_dataset,
)


def test_generate_bootstrap_dataset_shapes():
    X, y, w = generate_bootstrap_dataset(extract_features, n_cheaters=10, n_clean=10, n_borderline=5, seed=1)
    assert len(X) == len(y) == len(w) == 25


def test_temporal_json_roundtrip():
    t = TemporalPatternDetector()
    t.observe(["a", "b", "c"], label=1.0)
    loaded = TemporalPatternDetector.from_json(t.to_json())
    assert loaded.samples_observed == 1


def test_knn_remove_and_class_counts():
    knn = KNNCheaterClassifier(["x"], k=1, min_examples=1)
    knn.add_example(KNNExample("a", "A", [1.0], 1.0))
    knn.add_example(KNNExample("b", "B", [0.0], 0.0))
    counts = knn.class_counts()
    assert counts["cheaters"] == 1
    assert knn.remove_example("a") is True


def test_ensemble_predict_uses_multiple_components():
    lr = LogisticRegression(["x1", "x2"], seed=1)
    lr.samples_trained = 120
    knn = KNNCheaterClassifier(["x1", "x2"], k=1, min_examples=1)
    knn.add_example(KNNExample("u", "U", [1.0, 1.0], 1.0))
    t = TemporalPatternDetector()
    for _ in range(15):
        t.observe(["reach", "killaura"], 1.0)
    r = ensemble_predict([1.0, 1.0], ["reach", "killaura"], 0.6, lr, knn, t)
    assert 0.0 <= r.score <= 1.0
    assert "heuristic" in r.component_scores


def test_logreg_feature_importance_non_empty():
    m = LogisticRegression(["x1", "x2"], seed=1)
    imp = m.feature_importance()
    assert len(imp) > 0
