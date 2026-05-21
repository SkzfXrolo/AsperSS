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
    try:
        from config.hack_signatures import filename_is_definite_hack
    except ImportError:
        filename_is_definite_hack = None  # type: ignore

    for hive, path in KEYS:
        try:
            with winreg.OpenKey(hive, path) as key:
                total = winreg.QueryInfoKey(key)[1]
                for i in range(total):
                    name, value, _t = winreg.EnumValue(key, i)
                    low = str(value).lower()
                    name_low = str(name).lower()
                    combined = f"{name_low} {low}"
                    reason = None
                    if filename_is_definite_hack and filename_is_definite_hack(combined):
                        reason = "hack_client_reference"
                    elif any(t in low for t in suspicious_terms):
                        reason = "suspicious_value"
                    if reason:
                        findings.append({
                            "key": path,
                            "name": name,
                            "value": str(value)[:300],
                            "reason": reason,
                        })
        except Exception:
            continue
    return findings[:40]

