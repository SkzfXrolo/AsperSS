#!/usr/bin/env python3
import os
import random
import statistics
import sys
import time


ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
WEB_APP = os.path.join(ROOT, "web_app")
if WEB_APP not in sys.path:
    sys.path.insert(0, WEB_APP)

import argus_ai_features as F
import argus_ai_oracle as O
import argus_ai_trainer as T


def _percentile(values, q):
    idx = int(round((len(values) - 1) * q))
    idx = max(0, min(len(values) - 1, idx))
    return values[idx]


def _train_models(seed=48):
    X, y, w = T.generate_bootstrap_dataset(F.extract_features, n_cheaters=300, n_clean=300, n_borderline=150, seed=seed)
    lr = T.LogisticRegression(feature_names=F.FEATURE_NAMES, lr=0.05, l2=1e-4, seed=42)
    lr.fit(X, y, sample_weights=w, epochs=20, verbose=False)
    knn = T.KNNCheaterClassifier(feature_names=F.FEATURE_NAMES, k=7)
    for i in range(len(X)):
        if w[i] < 0.3:
            continue
        knn.add_example(T.KNNExample(player_uuid=f"bench_{i}", player_name=f"bench_{i}", feature_vector=X[i], label=y[i], weight=w[i], source="bench"))
    temporal = T.TemporalPatternDetector()
    rng = random.Random(seed)
    for _ in range(150):
        temporal.observe(F.extract_sequence(T._synth_cheater(rng)), 1.0)
    for _ in range(150):
        temporal.observe(F.extract_sequence(T._synth_clean(rng)), 0.0)
    return lr, knn, temporal


def main():
    n = 1000
    lr, knn, temporal = _train_models()
    rng = random.Random(480)
    lat_ms = []
    for _ in range(n):
        ev = T._synth_cheater(rng) if rng.random() < 0.5 else T._synth_clean(rng)
        seq = F.extract_sequence(ev)
        t0 = time.perf_counter()
        _ = O.evaluate_hybrid(ev, O.DEFAULT_WEIGHTS, log_reg=lr, knn=knn, temporal=temporal, sequence=seq)
        lat_ms.append((time.perf_counter() - t0) * 1000.0)

    lat_ms.sort()
    print("metric,value")
    print(f"n,{n}")
    print(f"avg_ms,{statistics.mean(lat_ms):.6f}")
    print(f"p50_ms,{_percentile(lat_ms, 0.50):.6f}")
    print(f"p95_ms,{_percentile(lat_ms, 0.95):.6f}")
    print(f"p99_ms,{_percentile(lat_ms, 0.99):.6f}")
    print(f"max_ms,{max(lat_ms):.6f}")


if __name__ == "__main__":
    main()
