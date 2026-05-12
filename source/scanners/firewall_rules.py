from __future__ import annotations

import subprocess


def scan_firewall_rules():
    findings = []
    try:
        r = subprocess.run(
            ["netsh", "advfirewall", "firewall", "show", "rule", "name=all"],
            capture_output=True,
            timeout=20,
            creationflags=0x08000000,
        )
        txt = (r.stdout or b"").decode("utf-8", errors="ignore")
    except Exception:
        txt = ""
    blocks = txt.split("Rule Name:")
    for b in blocks:
        low = b.lower()
        if "action: allow" in low and ("direction: out" in low or "remoteip: any" in low):
            findings.append({"rule": b.splitlines()[0].strip() if b.splitlines() else "", "reason": "broad_allow_rule"})
    return findings

