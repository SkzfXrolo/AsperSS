from __future__ import annotations

import os
import re


_PATTERNS = {
    "password_like": re.compile(r"(?i)\b(pass(word)?|pwd)\b.{0,20}[:=]\s*\S+"),
    "aws_key": re.compile(r"\bAKIA[0-9A-Z]{16}\b"),
    "github_pat": re.compile(r"\bgh[pousr]_[A-Za-z0-9_]{20,}\b"),
    "argus_token": re.compile(r"\bargus_[a-f0-9]{24,}\b", re.IGNORECASE),
    "btc_wallet": re.compile(r"\b[13][a-km-zA-HJ-NP-Z1-9]{25,34}\b"),
}


def scan_clipboard_history():
    base = os.path.join(os.environ.get("LOCALAPPDATA", ""), "Microsoft", "Windows", "Clipboard")
    findings = []
    if not os.path.isdir(base):
        return {"items": [], "findings": findings}
    items = []
    for root, _dirs, files in os.walk(base):
        for fname in files:
            path = os.path.join(root, fname)
            try:
                with open(path, "rb") as f:
                    data = f.read(32768)
                text = data.decode("utf-8", errors="ignore")
            except Exception:
                continue
            items.append(path)
            for tag, cre in _PATTERNS.items():
                if cre.search(text):
                    findings.append({"pattern": tag, "path": path})
    return {"items": items, "findings": findings}

