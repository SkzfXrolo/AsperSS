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
import argus_ai_trainer as T


def _estimate_dataset_mb(n_rows, n_features):
    # Aproximación simple: float64 para X + y + w
    bytes_x = n_rows * n_features * 8
    bytes_yw = n_rows * 2 * 8
    return (bytes_x + bytes_yw) / (1024.0 * 1024.0)


def _build_dataset(n, seed):
    rng = random.Random(seed)
    evs = []
    for _ in range(n):
        evs.append(T._synth_cheater(rng) if rng.random() < 0.5 else T._synth_clean(rng))
    X = [F.extract_features(ev) for ev in evs]
    y = [1.0 if ev.get("scan_detected_hacks_recent") else 0.0 for ev in evs]
    w = [1.0] * n
    return X, y, w


def _run_one(n):
    t0 = time.perf_counter()
    X, y, w = _build_dataset(n, seed=48 + n)
    t_data = (time.perf_counter() - t0) * 1000.0
    est_data_mb = _estimate_dataset_mb(n, len(F.FEATURE_NAMES))

    t1 = time.perf_counter()
    model = T.LogisticRegression(feature_names=F.FEATURE_NAMES, lr=0.05, l2=1e-4, seed=42)
    m = model.fit(X, y, sample_weights=w, epochs=3, verbose=False)
    t_train = (time.perf_counter() - t1) * 1000.0

    return {
        "samples": n,
        "build_ms": t_data,
        "train_ms": t_train,
        "total_ms": t_data + t_train,
        "est_data_mb": est_data_mb,
        "accuracy": float(m.get("accuracy", 0.0)),
    }


def main():
    sizes = [1_000, 10_000, 100_000]
    rows = [_run_one(n) for n in sizes]
    print("samples,build_ms,train_ms,total_ms,est_data_mb,accuracy")
    for r in rows:
        print(
            f"{r['samples']},{r['build_ms']:.3f},{r['train_ms']:.3f},{r['total_ms']:.3f},"
            f"{r['est_data_mb']:.3f},{r['accuracy']:.4f}"
        )


if __name__ == "__main__":
    main()
