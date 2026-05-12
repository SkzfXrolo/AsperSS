from __future__ import annotations

from argus_ai_trainer import KNNCheaterClassifier, KNNExample


def _build_knn():
    knn = KNNCheaterClassifier(feature_names=["x", "y"], k=3, min_examples=3)
    knn.add_example(KNNExample("c1", "c1", [1.0, 1.0], 1.0))
    knn.add_example(KNNExample("c2", "c2", [0.9, 1.1], 1.0))
    knn.add_example(KNNExample("c3", "c3", [1.1, 0.9], 1.0))
    knn.add_example(KNNExample("l1", "l1", [-1.0, -1.0], 0.0))
    knn.add_example(KNNExample("l2", "l2", [-1.1, -0.9], 0.0))
    knn.add_example(KNNExample("l3", "l3", [-0.9, -1.1], 0.0))
    return knn


def test_fit_predict_two_clear_clusters_k3():
    knn = _build_knn()
    cheater = knn.predict([1.0, 1.0])
    clean = knn.predict([-1.0, -1.0])
    assert cheater["score"] > 0.7
    assert clean["score"] < 0.3


def test_cosine_distance_behavior_prefers_same_direction():
    knn = _build_knn()
    a = knn.predict([2.0, 2.0])
    b = knn.predict([-2.0, -2.0])
    assert a["score"] > b["score"]


def test_less_examples_than_k_or_min_returns_fallback():
    knn = KNNCheaterClassifier(feature_names=["x", "y"], k=5, min_examples=3)
    knn.add_example(KNNExample("a", "a", [1, 1], 1.0))
    out = knn.predict([1, 1])
    assert out["score"] == 0.5
    assert out["confidence"] == 0.0


def test_wrong_feature_length_returns_fallback():
    knn = _build_knn()
    out = knn.predict([1.0])
    assert out["score"] == 0.5


def test_replace_example_same_uuid():
    knn = KNNCheaterClassifier(feature_names=["x", "y"])
    knn.add_example(KNNExample("u", "old", [0, 0], 0.0))
    knn.add_example(KNNExample("u", "new", [1, 1], 1.0))
    assert knn.size() == 1
    assert knn.examples[0].player_name == "new"


def test_neighbors_payload_is_present():
    knn = _build_knn()
    out = knn.predict([1.0, 1.0])
    assert isinstance(out["neighbors"], list)
