#!/usr/bin/env python3
import json
import sys
from pathlib import Path


SEV_MAP = {
    "low": "low",
    "medium": "medium",
    "high": "high",
    "critical": "critical",
}


def _norm_sev(v: str) -> str:
    return SEV_MAP.get((v or "").strip().lower(), "medium")


def parse_bandit(p):
    data = json.loads(Path(p).read_text(encoding="utf-8"))
    out = []
    for r in data.get("results", []):
        out.append({
            "tool": "bandit",
            "severity": _norm_sev(r.get("issue_severity")),
            "cwe": (r.get("issue_cwe") or {}).get("id"),
            "file": r.get("filename", ""),
            "line": int(r.get("line_number", 1)),
            "message": r.get("issue_text", ""),
            "fix_hint": "Review dangerous pattern and apply safer API.",
        })
    return out


def parse_semgrep(p):
    data = json.loads(Path(p).read_text(encoding="utf-8"))
    out = []
    for r in data.get("results", []):
        extra = r.get("extra", {})
        out.append({
            "tool": "semgrep",
            "severity": _norm_sev(extra.get("severity", "medium")),
            "cwe": None,
            "file": r.get("path", ""),
            "line": int((r.get("start") or {}).get("line", 1)),
            "message": extra.get("message", r.get("check_id", "")),
            "fix_hint": "Refactor code path to remove flagged anti-pattern.",
        })
    return out


def parse_gitleaks(p):
    data = json.loads(Path(p).read_text(encoding="utf-8"))
    out = []
    for r in data:
        out.append({
            "tool": "gitleaks",
            "severity": "high",
            "cwe": "CWE-798",
            "file": r.get("File", ""),
            "line": int(r.get("StartLine", 1)),
            "message": r.get("Description", "Potential secret found"),
            "fix_hint": "Rotate and remove secret from repository history.",
        })
    return out


def parse_pip_audit(p):
    data = json.loads(Path(p).read_text(encoding="utf-8"))
    out = []
    for dep in data.get("dependencies", []):
        for v in dep.get("vulns", []):
            out.append({
                "tool": "pip-audit",
                "severity": "high",
                "cwe": None,
                "file": "web_app/requirements.txt",
                "line": 1,
                "message": f"{dep.get('name')} {dep.get('version')} vulnerable: {v.get('id')}",
                "fix_hint": "Upgrade dependency to a fixed version.",
            })
    return out


def parse_safety(p):
    data = json.loads(Path(p).read_text(encoding="utf-8"))
    out = []
    if isinstance(data, list):
        for v in data:
            out.append({
                "tool": "safety",
                "severity": "high",
                "cwe": None,
                "file": "web_app/requirements.txt",
                "line": 1,
                "message": str(v),
                "fix_hint": "Upgrade affected package.",
            })
    return out


PARSERS = {
    "bandit": parse_bandit,
    "semgrep": parse_semgrep,
    "gitleaks": parse_gitleaks,
    "pip-audit": parse_pip_audit,
    "safety": parse_safety,
}


def main():
    if len(sys.argv) < 3:
        print("Usage: sast-parser.py <out.json> <tool=file.json> [tool=file.json ...]")
        sys.exit(2)
    out_file = sys.argv[1]
    merged = []
    for spec in sys.argv[2:]:
        tool, fp = spec.split("=", 1)
        if tool in PARSERS and Path(fp).exists():
            merged.extend(PARSERS[tool](fp))
    Path(out_file).write_text(json.dumps(merged, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"Wrote {len(merged)} findings -> {out_file}")


if __name__ == "__main__":
    main()
