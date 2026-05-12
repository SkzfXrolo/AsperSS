from __future__ import annotations

import subprocess


def _wmic(query):
    try:
        r = subprocess.run(["wmic", "/namespace:\\\\root\\subscription", "path", query, "get", "/format:list"], capture_output=True, timeout=12, creationflags=0x08000000)
        return (r.stdout or b"").decode("utf-8", errors="ignore")
    except Exception:
        return ""


def scan_wmi_subscriptions():
    filt = _wmic("__EventFilter")
    cons = _wmic("__EventConsumer")
    bind = _wmic("__FilterToConsumerBinding")
    return {"filters": filt[:4000], "consumers": cons[:4000], "bindings": bind[:4000]}

