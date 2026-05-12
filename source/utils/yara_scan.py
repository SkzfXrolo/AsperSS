from __future__ import annotations

from pathlib import Path


DEFAULT_RULES_DIR = Path(__file__).resolve().parents[1] / "yara_rules"


def scan_with_yara_rules(file_path, rules_path=None):
    """Escanea archivo con reglas YARA y maneja ausencia de yara-python."""
    try:
        import yara  # type: ignore
    except Exception:
        return []

    target = str(file_path)
    rules_loc = str(rules_path or DEFAULT_RULES_DIR)
    try:
        rules = yara.compile(filepath=rules_loc) if Path(rules_loc).is_file() else yara.compile(filepaths={"default": rules_loc})
        return rules.match(target)
    except Exception:
        return []

