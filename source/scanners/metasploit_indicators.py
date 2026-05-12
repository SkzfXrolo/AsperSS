from __future__ import annotations

import psutil


MSF_TERMS = ("meterpreter", "msfvenom", "reverse_tcp", "metasploit")


def scan_metasploit_indicators():
    findings = []
    for p in psutil.process_iter(["pid", "name", "cmdline"]):
        try:
            text = (" ".join(p.info.get("cmdline") or []) + " " + (p.info.get("name") or "")).lower()
            if any(t in text for t in MSF_TERMS):
                findings.append({"pid": p.info["pid"], "name": p.info.get("name", ""), "evidence": text[:220]})
        except Exception:
            continue
    return findings

