from __future__ import annotations

import os
import winreg


_RUN_KEYS = [
    (winreg.HKEY_LOCAL_MACHINE, r"Software\Microsoft\Windows\CurrentVersion\Run"),
    (winreg.HKEY_CURRENT_USER, r"Software\Microsoft\Windows\CurrentVersion\Run"),
    (winreg.HKEY_LOCAL_MACHINE, r"Software\Microsoft\Windows\CurrentVersion\RunOnce"),
    (winreg.HKEY_CURRENT_USER, r"Software\Microsoft\Windows\CurrentVersion\RunOnce"),
    (winreg.HKEY_LOCAL_MACHINE, r"Software\Microsoft\Windows\CurrentVersion\Policies\Explorer\Run"),
]


def _score(cmd):
    low = (cmd or "").lower()
    score = 0
    if any(x in low for x in ("\\appdata\\", "\\temp\\", "\\users\\public\\")):
        score += 2
    if "powershell" in low or "cmd /c" in low:
        score += 1
    return score


def scan_startup_locations():
    entries = []
    for hive, key_path in _RUN_KEYS:
        try:
            with winreg.OpenKey(hive, key_path) as k:
                total = winreg.QueryInfoKey(k)[1]
                for i in range(total):
                    name, value, _typ = winreg.EnumValue(k, i)
                    entries.append({"location": key_path, "name": name, "command": str(value), "score": _score(str(value))})
        except Exception:
            continue

    startup_dirs = [
        os.path.join(os.environ.get("APPDATA", ""), "Microsoft", "Windows", "Start Menu", "Programs", "Startup"),
        os.path.join(os.environ.get("PROGRAMDATA", ""), "Microsoft", "Windows", "Start Menu", "Programs", "Startup"),
    ]
    for sd in startup_dirs:
        if not os.path.isdir(sd):
            continue
        for fname in os.listdir(sd):
            full = os.path.join(sd, fname)
            entries.append({"location": sd, "name": fname, "command": full, "score": _score(full)})
    return entries

