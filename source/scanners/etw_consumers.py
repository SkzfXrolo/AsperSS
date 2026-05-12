from __future__ import annotations

import os
import subprocess


def scan_etw_consumers():
    suspicious = []
    try:
        r = subprocess.run(["logman", "query", "-ets"], capture_output=True, timeout=12, creationflags=0x08000000)
        out = (r.stdout or b"").decode("utf-8", errors="ignore")
    except Exception:
        out = ""
    for line in out.splitlines():
        low = line.lower()
        if ".etl" in low and any(x in low for x in ("\\temp\\", "\\appdata\\", "\\users\\")):
            suspicious.append({"entry": line.strip(), "reason": "etw_log_to_suspicious_path"})
    return {"raw": out[:5000], "suspicious": suspicious}

