from __future__ import annotations

import winreg


def scan_uac_bypass():
    findings = []
    keys = [
        r"Software\Classes\ms-settings\shell\open\command",
        r"Software\Classes\mscfile\shell\open\command",
    ]
    for key in keys:
        try:
            with winreg.OpenKey(winreg.HKEY_CURRENT_USER, key) as k:
                val, _ = winreg.QueryValueEx(k, None)
                if val:
                    findings.append({"key": key, "value": str(val), "reason": "uac_bypass_artifact"})
        except Exception:
            continue
    return findings

