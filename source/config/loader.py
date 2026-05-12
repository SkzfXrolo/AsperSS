from __future__ import annotations

import json
from pathlib import Path

from config.defaults import DEFAULT_CONFIG


def load_config(path: str | None = None):
    cfg = dict(DEFAULT_CONFIG)
    if not path:
        return cfg
    p = Path(path)
    if not p.is_file():
        return cfg
    text = p.read_text(encoding="utf-8", errors="ignore")
    if p.suffix.lower() in (".yaml", ".yml"):
        parsed = {}
        for line in text.splitlines():
            if ":" in line and not line.strip().startswith("#"):
                k, v = line.split(":", 1)
                parsed[k.strip()] = v.strip().strip("'\"")
    else:
        parsed = json.loads(text or "{}")
    cfg.update(parsed)
    return cfg

