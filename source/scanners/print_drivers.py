from __future__ import annotations

import subprocess


def scan_print_drivers():
    findings = []
    try:
        r = subprocess.run(["pnputil", "/enum-drivers"], capture_output=True, timeout=20, creationflags=0x08000000)
        txt = (r.stdout or b"").decode("utf-8", errors="ignore")
    except Exception:
        txt = ""
    for line in txt.splitlines():
        low = line.lower()
        if "print" in low and any(x in low for x in ("temp", "appdata", "users\\")):
            findings.append({"entry": line.strip(), "reason": "print_driver_suspicious_path"})
    return findings

