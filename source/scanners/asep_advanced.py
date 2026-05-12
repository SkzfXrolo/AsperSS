from __future__ import annotations

import winreg


ASEP_KEYS = [
    r"Software\Microsoft\Windows\CurrentVersion\Run",
    r"Software\Microsoft\Windows\CurrentVersion\RunOnce",
    r"Software\Microsoft\Windows NT\CurrentVersion\Winlogon",
    r"Software\Microsoft\Windows NT\CurrentVersion\Windows",
]


def scan_asep_advanced():
    findings = []
    for key in ASEP_KEYS:
        for hive in (winreg.HKEY_LOCAL_MACHINE, winreg.HKEY_CURRENT_USER):
            try:
                with winreg.OpenKey(hive, key) as k:
                    n = winreg.QueryInfoKey(k)[1]
                    for i in range(n):
                        name, val, _ = winreg.EnumValue(k, i)
                        findings.append({"key": key, "name": name, "value": str(val)})
            except Exception:
                continue
    return findings

