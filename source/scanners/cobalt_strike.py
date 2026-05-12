from __future__ import annotations

import psutil


CS_TERMS = ("beacon", "teamserver", "artifactkit", "malleable")


def scan_cobalt_strike_indicators():
    findings = []
    for p in psutil.process_iter(["pid", "name", "cmdline"]):
        try:
            joined = (" ".join(p.info.get("cmdline") or []) + " " + (p.info.get("name") or "")).lower()
            if any(t in joined for t in CS_TERMS):
                findings.append({"pid": p.info["pid"], "name": p.info.get("name", ""), "evidence": joined[:220]})
        except Exception:
            continue
    return findings

