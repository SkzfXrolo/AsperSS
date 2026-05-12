from __future__ import annotations

import os


SUS_DLLS = {"version.dll", "winmm.dll", "dwmapi.dll", "dbghelp.dll"}


def scan_dll_search_order():
    findings = []
    roots = [r"C:\Program Files", r"C:\Program Files (x86)", os.environ.get("APPDATA", "")]
    for root in roots:
        if not root or not os.path.isdir(root):
            continue
        for dp, _dirs, files in os.walk(root):
            l = {f.lower() for f in files}
            if not any(f.endswith(".exe") for f in l):
                continue
            for dll in SUS_DLLS:
                if dll in l and "\\windows\\system32\\" not in dp.lower():
                    findings.append({"dir": dp, "dll": dll, "reason": "search_order_hijack_candidate"})
    return findings

