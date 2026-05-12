from __future__ import annotations

import os
import subprocess
import time


def scan_anti_forensics():
    findings = []
    try:
        sec = subprocess.run(
            ["wevtutil", "qe", "Security", "/q:*[System[(EventID=1102)]]", "/c:30", "/rd:true", "/f:text"],
            capture_output=True, timeout=10, creationflags=0x08000000
        )
        if (sec.stdout or b"").strip():
            findings.append({"type": "eventlog_cleared_security_1102"})
    except Exception:
        pass
    try:
        sys = subprocess.run(
            ["wevtutil", "qe", "System", "/q:*[System[(EventID=104)]]", "/c:30", "/rd:true", "/f:text"],
            capture_output=True, timeout=10, creationflags=0x08000000
        )
        if (sys.stdout or b"").strip():
            findings.append({"type": "eventlog_cleared_system_104"})
    except Exception:
        pass

    system32 = os.path.join(os.environ.get("WINDIR", r"C:\Windows"), "System32")
    if os.path.isdir(system32):
        now = time.time()
        for fname in ("svchost.exe", "lsass.exe", "services.exe"):
            p = os.path.join(system32, fname)
            try:
                st = os.stat(p)
                if st.st_mtime < st.st_ctime and (now - st.st_ctime) < 86400 * 30:
                    findings.append({"type": "timestomp_suspected", "path": p})
            except Exception:
                continue
    return findings

