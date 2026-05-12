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


def _percentile(values, q):
    if not values:
        return 0.0
    idx = int(round((len(values) - 1) * q))
    idx = max(0, min(len(values) - 1, idx))
    return values[idx]


def main():
    n = 10_000
    rng = random.Random(48)
    lat_ms = []
    for _ in range(n):
        ev = T._synth_cheater(rng) if rng.random() < 0.5 else T._synth_clean(rng)
        t0 = time.perf_counter()
        _ = F.extract_features(ev)
        lat_ms.append((time.perf_counter() - t0) * 1000.0)

    lat_ms.sort()
    total_ms = sum(lat_ms)
    print("metric,value")
    print(f"n,{n}")
    print(f"total_ms,{total_ms:.3f}")
    print(f"avg_ms,{statistics.mean(lat_ms):.6f}")
    print(f"p50_ms,{_percentile(lat_ms, 0.50):.6f}")
    print(f"p95_ms,{_percentile(lat_ms, 0.95):.6f}")
    print(f"p99_ms,{_percentile(lat_ms, 0.99):.6f}")
    print(f"ops_per_sec,{(1000.0 / statistics.mean(lat_ms)):.2f}")


if __name__ == "__main__":
    main()
