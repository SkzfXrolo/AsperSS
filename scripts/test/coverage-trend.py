from __future__ import annotations

from pathlib import Path


def main() -> None:
    Path("tests/coverage-trend.md").write_text("# Coverage trend\n\nPendiente integrar histórico.\n", encoding="utf-8")


if __name__ == "__main__":
    main()
