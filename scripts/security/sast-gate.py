#!/usr/bin/env python3
import json
import sys
from pathlib import Path


ORDER = {"low": 1, "medium": 2, "high": 3, "critical": 4}


def main():
    if len(sys.argv) < 2:
        print("Usage: sast-gate.py <unified.json> [threshold_count]")
        sys.exit(2)
    path = Path(sys.argv[1])
    threshold = int(sys.argv[2]) if len(sys.argv) > 2 else 0
    data = json.loads(path.read_text(encoding="utf-8"))
    bad = [f for f in data if ORDER.get(f.get("severity", "low"), 1) >= ORDER["high"]]
    print(f"Findings high+ : {len(bad)}")
    if len(bad) > threshold:
        print("Gate failed.")
        sys.exit(1)
    print("Gate passed.")


if __name__ == "__main__":
    main()
