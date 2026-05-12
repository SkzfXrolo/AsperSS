from __future__ import annotations

import json
from pathlib import Path


def main() -> None:
    src = Path("coverage.json")
    if not src.exists():
        Path("tests/coverage-gaps.md").write_text("# Coverage gaps\n\nNo coverage.json found.\n", encoding="utf-8")
        return
    data = json.loads(src.read_text(encoding="utf-8"))
    Path("tests/coverage-gaps.md").write_text(f"# Coverage gaps\n\nFiles: {len(data.get('files', {}))}\n", encoding="utf-8")


if __name__ == "__main__":
    main()
