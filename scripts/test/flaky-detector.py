from __future__ import annotations

import subprocess
import sys


def main() -> int:
    target = sys.argv[1] if len(sys.argv) > 1 else "tests/test_oracle_evaluate.py"
    results = []
    for _ in range(5):
        proc = subprocess.run([sys.executable, "-m", "pytest", target, "-q"], capture_output=True, text=True)
        results.append(proc.returncode == 0)
    print({"target": target, "passes": sum(results), "runs": 5, "flaky": len(set(results)) > 1})
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
