from __future__ import annotations

import sys


def parse(lines: list[str]) -> str:
    survived = [l for l in lines if "survived" in l.lower()]
    killed = [l for l in lines if "killed" in l.lower()]
    out = [
        "# Mutation report",
        f"- Killed: {len(killed)}",
        f"- Survived: {len(survived)}",
        "",
        "## Survived mutants",
    ]
    out.extend(f"- {s.strip()}" for s in survived[:200])
    return "\n".join(out) + "\n"


def main():
    lines = sys.stdin.read().splitlines()
    print(parse(lines))


if __name__ == "__main__":
    main()
