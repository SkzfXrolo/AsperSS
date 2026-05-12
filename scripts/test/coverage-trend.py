from __future__ import annotations

import json
from pathlib import Path


def main() -> None:
    p = Path("coverage.json")
    md = Path("tests/coverage-trend.md")
    if not p.exists():
        md.write_text("# Coverage trend\n\nNo coverage.json found.\n", encoding="utf-8")
        return
    data = json.loads(p.read_text(encoding="utf-8"))
    md.write_text(f"# Coverage trend\n\nfiles: {len(data.get('files', {}))}\n", encoding="utf-8")


if __name__ == "__main__":
    main()
