from __future__ import annotations

from pathlib import Path


DEFAULT_RULES_DIR = Path(__file__).resolve().parents[1] / "yara_rules"


def _collect_rule_files(rules_path) -> list[Path]:
    loc = Path(rules_path)
    if loc.is_file() and loc.suffix.lower() in (".yar", ".yara"):
        return [loc]
    if loc.is_dir():
        files = sorted(loc.glob("*.yar")) + sorted(loc.glob("*.yara"))
        return files
    return []


def scan_with_yara_rules(file_path, rules_path=None):
    """Escanea archivo con reglas YARA y maneja ausencia de yara-python."""
    try:
        import yara  # type: ignore
    except Exception:
        return []

    target = str(file_path)
    rules_loc = Path(rules_path or DEFAULT_RULES_DIR)
    try:
        if rules_loc.is_file():
            rules = yara.compile(filepath=str(rules_loc))
        else:
            files = _collect_rule_files(rules_loc)
            if not files:
                return []
            filepaths = {f"r{i}": str(p) for i, p in enumerate(files)}
            rules = yara.compile(filepaths=filepaths)
        return rules.match(target)
    except Exception:
        return []
