from __future__ import annotations

import os
import re
import subprocess


def scan_services_anomalies():
    suspicious = []
    try:
        r = subprocess.run(["sc", "query", "state=", "all"], capture_output=True, timeout=18, creationflags=0x08000000)
        names = re.findall(r"SERVICE_NAME:\s+([^\r\n]+)", (r.stdout or b"").decode("utf-8", errors="ignore"))
    except Exception:
        names = []

    for name in names[:400]:
        try:
            qc = subprocess.run(["sc", "qc", name], capture_output=True, timeout=8, creationflags=0x08000000)
            txt = (qc.stdout or b"").decode("utf-8", errors="ignore")
        except Exception:
            continue
        low = txt.lower()
        m = re.search(r"binary_path_name\s*:\s*(.+)", txt, re.IGNORECASE)
        path = (m.group(1).strip() if m else "").strip('"')
        if any(k in low for k in ("\\appdata\\", "\\temp\\")):
            suspicious.append({"service": name, "path": path, "reason": "suspicious_path"})
    return {"total_services": len(names), "suspicious": suspicious}

