from __future__ import annotations

import json
import sys

from argus_ai_oracle import evaluate


def run_one(data: bytes):
    try:
        obj = json.loads(data.decode("utf-8", errors="ignore") or "{}")
        if not isinstance(obj, dict):
            obj = {"violations": []}
    except Exception:
        obj = {"violations": []}
    evaluate(obj)


def main():
    data = sys.stdin.buffer.read()
    run_one(data)


if __name__ == "__main__":
    main()
