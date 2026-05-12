from __future__ import annotations

import winreg


def scan_com_objects():
    findings = []
    base = r"SOFTWARE\Classes\CLSID"
    bad = ("\\appdata\\", "\\temp\\", "\\users\\", "\\programdata\\")
    try:
        with winreg.OpenKey(winreg.HKEY_LOCAL_MACHINE, base) as root:
            i = 0
            while True:
                try:
                    clsid = winreg.EnumKey(root, i)
                    i += 1
                except OSError:
                    break
                for sub in ("InprocServer32", "LocalServer32"):
                    try:
                        with winreg.OpenKey(winreg.HKEY_LOCAL_MACHINE, f"{base}\\{clsid}\\{sub}") as sk:
                            val, _ = winreg.QueryValueEx(sk, None)
                            low = str(val).lower()
                            if any(b in low for b in bad):
                                findings.append({"clsid": clsid, "subkey": sub, "path": str(val)})
                    except Exception:
                        continue
    except Exception:
        pass
    return findings

