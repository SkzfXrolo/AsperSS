from __future__ import annotations

import psutil


MINER_NAMES = ("xmrig", "cpuminer", "miner", "ethminer")


def scan_cryptojacking(cpu_threshold=70.0):
    findings = []
    for p in psutil.process_iter(["pid", "name", "cpu_percent", "exe"]):
        try:
            name = (p.info.get("name") or "").lower()
            cpu = float(p.info.get("cpu_percent") or 0.0)
            if any(m in name for m in MINER_NAMES) or cpu >= cpu_threshold:
                findings.append({"pid": p.info["pid"], "name": name, "cpu": cpu, "exe": p.info.get("exe", "")})
        except Exception:
            continue
    return findings

