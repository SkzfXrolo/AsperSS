from __future__ import annotations

import re
import subprocess


def read_sysmon_events(event_id: int | None = None, max_events: int = 100):
    query = "*"
    if event_id is not None:
        query = f"*[System[(EventID={int(event_id)})]]"
    try:
        r = subprocess.run(
            ["wevtutil", "qe", "Microsoft-Windows-Sysmon/Operational", f"/q:{query}", f"/c:{int(max_events)}", "/rd:true", "/f:text"],
            capture_output=True,
            timeout=15,
            creationflags=0x08000000,
        )
        return (r.stdout or b"").decode("utf-8", errors="ignore")
    except Exception:
        return ""


def parse_process_create(raw_text: str):
    out = []
    chunks = raw_text.split("Event[")
    for c in chunks:
        if "event id: 1" in c.lower():
            image = re.search(r"image:\s*(.+)", c, re.IGNORECASE)
            cmd = re.search(r"commandline:\s*(.+)", c, re.IGNORECASE)
            out.append({"image": image.group(1).strip() if image else "", "commandline": cmd.group(1).strip() if cmd else ""})
    return out

