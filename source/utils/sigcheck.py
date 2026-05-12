from __future__ import annotations

import subprocess


def verify_signature(path: str) -> dict:
    try:
        cmd = f"(Get-AuthenticodeSignature -LiteralPath '{path}').Status"
        r = subprocess.run(["powershell", "-NoProfile", "-Command", cmd], capture_output=True, timeout=8, creationflags=0x08000000)
        status = (r.stdout or b"").decode("utf-8", errors="ignore").strip()
    except Exception:
        status = "UnknownError"
    return {"path": path, "status": status, "valid": status.lower() == "valid"}

