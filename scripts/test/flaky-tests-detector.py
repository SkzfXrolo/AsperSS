from __future__ import annotations

from pathlib import Path


def main() -> None:
    Path("tests/flaky-tests.md").write_text("# Flaky tests\n\nSin data histórica aún.\n", encoding="utf-8")


if __name__ == "__main__":
    main()
