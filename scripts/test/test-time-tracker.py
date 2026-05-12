from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path


def main() -> int:
    out = Path("tests/time-report.json")
    proc = subprocess.run([sys.executable, "-m", "pytest", "tests/", "--durations=25", "-q"], capture_output=True, text=True)
    out.write_text(json.dumps({"returncode": proc.returncode, "stdout": proc.stdout[-4000:]}, indent=2), encoding="utf-8")
    print(f"saved {out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
