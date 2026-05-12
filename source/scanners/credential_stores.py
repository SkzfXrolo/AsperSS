from __future__ import annotations

import os
import winreg


def scan_credential_stores():
    findings = []
    try:
        with winreg.OpenKey(winreg.HKEY_LOCAL_MACHINE, r"SECURITY\Policy\Secrets") as k:
            subcount = winreg.QueryInfoKey(k)[0]
            findings.append({"type": "lsa_secrets_accessible", "count": subcount})
    except Exception:
        pass

    vault_dir = os.path.join(os.environ.get("LOCALAPPDATA", ""), "Microsoft", "Vault")
    if os.path.isdir(vault_dir):
        for root, _dirs, files in os.walk(vault_dir):
            for f in files:
                if f.lower().endswith((".vcrd", ".vpol")):
                    findings.append({"type": "vault_file", "path": os.path.join(root, f)})
    return findings

