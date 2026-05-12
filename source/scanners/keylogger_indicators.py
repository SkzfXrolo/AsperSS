from __future__ import annotations

import psutil


HIT_TERMS = ("keylog", "keyboardhook", "setwindowshook", "lowlevelkeyboardproc")


def scan_keylogger_indicators():
    findings = []
    for p in psutil.process_iter(["pid", "name", "cmdline"]):
        try:
            cmd = " ".join(p.info.get("cmdline") or []).lower()
            name = (p.info.get("name") or "").lower()
            if any(t in cmd or t in name for t in HIT_TERMS):
                findings.append({"pid": p.info["pid"], "name": name, "cmdline": cmd})
        except Exception:
            continue
    return findings

