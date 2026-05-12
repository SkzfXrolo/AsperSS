#!/usr/bin/env python3
import json
import time


DATA = {"player": "bench", "score": 0.91, "checks": ["reach", "killaura"], "n": list(range(200))}


def bench_json(rounds=10000):
    t0 = time.perf_counter()
    for _ in range(rounds):
        s = json.dumps(DATA)
        _ = json.loads(s)
    return (time.perf_counter() - t0) * 1000


if __name__ == "__main__":
    ms = bench_json()
    print("codec,total_ms")
    print(f"json,{ms:.3f}")
    print("# MessagePack/Protobuf: integrar cuando haya dependencias instaladas.")
