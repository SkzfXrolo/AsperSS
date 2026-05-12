from __future__ import annotations

import os


RANSOM_EXT = (".locked", ".crypted", ".crypt", ".enc", ".ryk")
RANSOM_NOTES = {"readme_decrypt.txt", "how_to_decrypt.txt", "recover-files.txt"}


def scan_ransomware_indicators(root=None):
    root = root or os.environ.get("USERPROFILE", r"C:\Users\Public")
    findings = []
    if not os.path.isdir(root):
        return findings
    for dp, _dirs, files in os.walk(root):
        for f in files:
            low = f.lower()
            if low.endswith(RANSOM_EXT):
                findings.append({"path": os.path.join(dp, f), "reason": "ransom_extension"})
            if low in RANSOM_NOTES:
                findings.append({"path": os.path.join(dp, f), "reason": "ransom_note"})
    return findings

