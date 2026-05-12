from __future__ import annotations

import os
import subprocess


def scan_lateral_movement_indicators():
    findings = []
    try:
        r = subprocess.run(["sc", "queryex", "PSEXESVC"], capture_output=True, timeout=6, creationflags=0x08000000)
        txt = (r.stdout or b"").decode("utf-8", errors="ignore").lower()
        if "service_name" in txt:
            findings.append({"type": "psexec_residual", "detail": "PSEXESVC detectado"})
    except Exception:
        pass

    try:
        n = subprocess.run(["netstat", "-ano"], capture_output=True, timeout=10, creationflags=0x08000000)
        out = (n.stdout or b"").decode("utf-8", errors="ignore")
        for line in out.splitlines():
            if ":445" in line or ":139" in line:
                findings.append({"type": "smb_recent_connection", "detail": line.strip()})
    except Exception:
        pass

    pipe_base = "\\\\.\\pipe\\"
    try:
        for p in os.listdir(pipe_base):
            low = p.lower()
            if "psexec" in low or "remcom" in low:
                findings.append({"type": "sysinternals_pipe", "detail": p})
    except Exception:
        pass
    return findings

