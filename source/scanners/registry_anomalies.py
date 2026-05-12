from __future__ import annotations

import winreg


KEYS = [
    (winreg.HKEY_LOCAL_MACHINE, r"Software\Microsoft\Windows\CurrentVersion\Run"),
    (winreg.HKEY_CURRENT_USER, r"Software\Microsoft\Windows\CurrentVersion\RunOnce"),
    (winreg.HKEY_LOCAL_MACHINE, r"Software\Microsoft\Windows NT\CurrentVersion\Image File Execution Options"),
    (winreg.HKEY_LOCAL_MACHINE, r"Software\Microsoft\Windows NT\CurrentVersion\Windows"),
    (winreg.HKEY_LOCAL_MACHINE, r"Software\Microsoft\Windows NT\CurrentVersion\Winlogon"),
]


def scan_registry_anomalies():
    findings = []
    suspicious_terms = ("appdata", "temp", "powershell", "cmd /c", "rundll32")
    for hive, path in KEYS:
        try:
            with winreg.OpenKey(hive, path) as key:
                total = winreg.QueryInfoKey(key)[1]
                for i in range(total):
                    name, value, _t = winreg.EnumValue(key, i)
                    low = str(value).lower()
                    if any(t in low for t in suspicious_terms):
                        findings.append({"key": path, "name": name, "value": str(value), "reason": "suspicious_value"})
        except Exception:
            continue
    return findings

