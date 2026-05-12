from __future__ import annotations

import os
import re


def scan_scheduled_task_xml():
    base = r"C:\Windows\System32\Tasks"
    findings = []
    if not os.path.isdir(base):
        return findings
    for root, _dirs, files in os.walk(base):
        for f in files:
            p = os.path.join(root, f)
            try:
                text = open(p, "r", encoding="utf-16-le", errors="ignore").read(65536).lower()
            except Exception:
                try:
                    text = open(p, "r", encoding="utf-8", errors="ignore").read(65536).lower()
                except Exception:
                    continue
            triggers = re.findall(r"<scheduleby([a-z]+)>", text)
            command = re.findall(r"<command>([^<]+)</command>", text)
            suspicious = any(t in text for t in ("appdata", "temp", "powershell -enc", "mshta"))
            if suspicious or triggers:
                findings.append({"task": p, "triggers": triggers[:5], "command": command[:2], "suspicious": suspicious})
    return findings

