from __future__ import annotations

import psutil


CAPTURE_TERMS = ("gdigrab", "dxgi", "screenshot", "capture", "obs", "ffmpeg")


def scan_screen_capture_indicators():
    findings = []
    for p in psutil.process_iter(["pid", "name", "cmdline"]):
        try:
            data = ((p.info.get("name") or "") + " " + " ".join(p.info.get("cmdline") or [])).lower()
            if any(t in data for t in CAPTURE_TERMS):
                findings.append({"pid": p.info["pid"], "name": p.info.get("name", ""), "detail": data[:200]})
        except Exception:
            continue
    return findings

