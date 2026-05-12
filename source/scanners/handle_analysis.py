from __future__ import annotations

import shutil
import subprocess


def scan_process_handles():
    handle_exe = shutil.which("handle.exe")
    if not handle_exe:
        return {"available": False, "suspicious": []}
    try:
        r = subprocess.run([handle_exe, "-nobanner"], capture_output=True, timeout=20, creationflags=0x08000000)
        out = (r.stdout or b"").decode("utf-8", errors="ignore")
    except Exception:
        return {"available": True, "suspicious": []}

    suspicious = []
    for line in out.splitlines():
        low = line.lower()
        if "process" in low and any(k in low for k in ("lsass.exe", "winlogon.exe", "csrss.exe")) and "pid:" in low:
            suspicious.append({"entry": line.strip(), "reason": "sensitive_process_handle"})
    return {"available": True, "suspicious": suspicious}

