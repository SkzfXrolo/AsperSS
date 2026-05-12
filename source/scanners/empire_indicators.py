from __future__ import annotations

import psutil


EMPIRE_TERMS = ("empire", "invoke-empire", "stager", "powershell -w hidden -enc")


def scan_empire_indicators():
    findings = []
    for p in psutil.process_iter(["pid", "name", "cmdline"]):
        try:
            cmd = " ".join(p.info.get("cmdline") or []).lower()
            if any(t in cmd for t in EMPIRE_TERMS):
                findings.append({"pid": p.info["pid"], "cmdline": cmd[:240]})
        except Exception:
            continue
    return findings

