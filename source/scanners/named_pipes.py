from __future__ import annotations

import os


SUSPICIOUS_PREFIX = ("\\\\.\\pipe\\msagent_", "\\\\.\\pipe\\postex_", "\\\\.\\pipe\\status_")


def scan_named_pipes():
    base = "\\\\.\\pipe\\"
    pipes = []
    suspicious = []
    try:
        for name in os.listdir(base):
            full = f"\\\\.\\pipe\\{name}"
            pipes.append(full)
            low = full.lower()
            if any(low.startswith(p.lower()) for p in SUSPICIOUS_PREFIX):
                suspicious.append({"pipe": full, "reason": "known_c2_pattern"})
    except Exception:
        pass
    return {"pipes": pipes, "suspicious": suspicious}

