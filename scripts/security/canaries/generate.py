#!/usr/bin/env python3
import secrets
import sys


def generate(n=5):
    return [f"argus_canary_{secrets.token_urlsafe(18)}" for _ in range(n)]


if __name__ == "__main__":
    count = int(sys.argv[1]) if len(sys.argv) > 1 else 5
    for t in generate(count):
        print(t)
