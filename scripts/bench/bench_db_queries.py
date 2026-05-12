#!/usr/bin/env python3
import random
import time


def mock_query_cost(rows: int) -> float:
    t0 = time.perf_counter()
    _ = sorted((random.random() for _ in range(rows)))
    return (time.perf_counter() - t0) * 1000


def main():
    sizes = [100, 1000, 5000]
    print("rows,latency_ms")
    for n in sizes:
        print(f"{n},{mock_query_cost(n):.3f}")


if __name__ == "__main__":
    main()
