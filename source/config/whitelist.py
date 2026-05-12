from __future__ import annotations

import json
from pathlib import Path


def load_whitelist(path: str):
    p = Path(path)
    if not p.is_file():
        return []
    try:
        return list(json.loads(p.read_text(encoding="utf-8")))
    except Exception:
        return []


def is_whitelisted(value: str, whitelist: list[str]):
    low = (value or "").lower()
    return any(w.lower() in low for w in whitelist or [])

