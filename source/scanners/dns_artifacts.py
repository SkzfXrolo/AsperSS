from __future__ import annotations

import os
import re
import subprocess


def scan_dns_artifacts():
    out = {"dns_cache": [], "hosts_entries": [], "doh_dot_anomalies": []}
    try:
        r = subprocess.run(["ipconfig", "/displaydns"], capture_output=True, timeout=12, creationflags=0x08000000)
        txt = (r.stdout or b"").decode("utf-8", errors="ignore")
        out["dns_cache"] = [ln.strip() for ln in txt.splitlines() if "record name" in ln.lower()]
    except Exception:
        pass

    hosts = r"C:\Windows\System32\drivers\etc\hosts"
    if os.path.isfile(hosts):
        try:
            with open(hosts, "r", encoding="utf-8", errors="ignore") as f:
                for ln in f:
                    s = ln.strip()
                    if s and not s.startswith("#"):
                        out["hosts_entries"].append(s)
        except Exception:
            pass

    for entry in out["hosts_entries"]:
        if re.search(r"\b(1\.1\.1\.1|8\.8\.8\.8|9\.9\.9\.9)\b", entry):
            out["doh_dot_anomalies"].append({"entry": entry, "reason": "public_dns_override"})
    return out

