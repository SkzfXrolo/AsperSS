from __future__ import annotations

import re
import subprocess


BLOCKLIST_IPS = {"45.9.148.108", "185.225.69.69", "103.27.202.0"}


def _run(cmd):
    try:
        r = subprocess.run(cmd, capture_output=True, timeout=12, creationflags=0x08000000)
        return (r.stdout or b"").decode("utf-8", errors="ignore")
    except Exception:
        return ""


def scan_network_state():
    results = {
        "arp_entries": [],
        "routes": [],
        "listening_ports": [],
        "established_connections": [],
        "suspicious_connections": [],
    }
    arp = _run(["arp", "-a"])
    for line in arp.splitlines():
        if re.search(r"\b\d{1,3}(?:\.\d{1,3}){3}\b", line):
            results["arp_entries"].append(line.strip())

    route = _run(["route", "print"])
    for line in route.splitlines():
        if re.search(r"\b\d{1,3}(?:\.\d{1,3}){3}\b", line):
            results["routes"].append(line.strip())

    net = _run(["netstat", "-ano"])
    for line in net.splitlines():
        low = line.lower().strip()
        if "listen" in low:
            results["listening_ports"].append(line.strip())
        if "established" in low:
            results["established_connections"].append(line.strip())
            for ip in BLOCKLIST_IPS:
                if ip in low:
                    results["suspicious_connections"].append({"ip": ip, "entry": line.strip()})
    return results

