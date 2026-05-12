from __future__ import annotations

import json
from pathlib import Path


def main() -> None:
    report = {
        "suite": "Pack48",
        "status": "generated",
    }
    Path("tests/report-summary.json").write_text(json.dumps(report, indent=2), encoding="utf-8")


if __name__ == "__main__":
    main()
