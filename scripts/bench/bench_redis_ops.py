#!/usr/bin/env python3
import time


def main():
    n = 100000
    d = {}
    t0 = time.perf_counter()
    for i in range(n):
        d[i] = i
    for i in range(n):
        _ = d.get(i)
    ms = (time.perf_counter() - t0) * 1000
    print("ops,total_ms,ops_per_sec")
    print(f"{2*n},{ms:.3f},{(2*n)/(ms/1000):.2f}")


if __name__ == "__main__":
    main()
