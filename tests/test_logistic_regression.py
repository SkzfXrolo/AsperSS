from __future__ import annotations

import random

from argus_ai_trainer import LogisticRegression


def _separable_dataset(n=120, seed=7):
    rng = random.Random(seed)
    X, y = [], []
    for _ in range(n // 2):
        X.append([rng.uniform(1.5, 3.0), rng.uniform(1.0, 2.5)])
        y.append(1.0)
    for _ in range(n // 2):
        X.append([rng.uniform(-3.0, -1.5), rng.uniform(-2.5, -1.0)])
        y.append(0.0)
    return X, y


def _accuracy(m, X, y):
    good = 0
    for xi, yi in zip(X, y):
        pred = 1.0 if m.predict_proba(xi) >= 0.5 else 0.0
        if pred == yi:
            good += 1
    return good / len(y)


def test_fit_separable_dataset_gets_high_accuracy():
    X, y = _separable_dataset()
    m = LogisticRegression(["x1", "x2"], lr=0.08, l2=1e-4, seed=1)
    m.fit(X, y, epochs=50)
    assert _accuracy(m, X, y) > 0.95


def test_fit_impossible_dataset_does_not_crash():
    X = [[0.0, 0.0]] * 20
    y = [0.0, 1.0] * 10
    m = LogisticRegression(["x1", "x2"], lr=0.05, seed=2)
    out = m.fit(X, y, epochs=10)
    assert "accuracy" in out


def test_predict_proba_is_in_range():
    X, y = _separable_dataset()
    m = LogisticRegression(["x1", "x2"], seed=3)
    m.fit(X, y, epochs=5)
    p = m.predict_proba([0.1, -0.2])
    assert 0.0 <= p <= 1.0


def test_platt_scaling_is_updated_after_fit():
    X, y = _separable_dataset(80)
    m = LogisticRegression(["x1", "x2"], seed=4)
    a0, b0 = m.platt_a, m.platt_b
    m.fit(X, y, epochs=25)
    assert (m.platt_a, m.platt_b) != (a0, b0)


def test_l2_regularization_reduces_weight_magnitude():
    X, y = _separable_dataset(100, seed=11)
    no_l2 = LogisticRegression(["x1", "x2"], l2=0.0, seed=5)
    with_l2 = LogisticRegression(["x1", "x2"], l2=0.2, seed=5)
    no_l2.fit(X, y, epochs=40)
    with_l2.fit(X, y, epochs=40)
    mag_no = sum(abs(w) for w in no_l2.weights)
    mag_l2 = sum(abs(w) for w in with_l2.weights)
    assert mag_l2 < mag_no


def test_malformed_input_returns_uncertain_half():
    m = LogisticRegression(["x1", "x2"], seed=6)
    assert m.predict_proba([1.0]) == 0.5


def test_json_roundtrip_preserves_shape():
    X, y = _separable_dataset(40)
    m = LogisticRegression(["x1", "x2"], seed=9)
    m.fit(X, y, epochs=8)
    loaded = LogisticRegression.from_json(m.to_json())
    assert loaded.n == m.n
    assert len(loaded.weights) == len(m.weights)
