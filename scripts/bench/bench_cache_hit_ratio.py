#!/usr/bin/env python3
import random


def main():
    cache = {}
    hits = 0
    total = 10000
    for _ in range(total):
        k = random.randint(1, 1000)
        if k in cache:
            hits += 1
        else:
            cache[k] = 1
    ratio = hits / total
    print("metric,value")
    print(f"total,{total}")
    print(f"hits,{hits}")
    print(f"hit_ratio,{ratio:.4f}")


if __name__ == "__main__":
    main()
