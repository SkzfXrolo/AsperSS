from __future__ import annotations

import hashlib
import os
import subprocess


def _hash_file(path, algo):
    h = hashlib.new(algo)
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(65536), b""):
            h.update(chunk)
    return h.hexdigest()


def get_file_metadata(path):
    st = os.stat(path)
    signature = "unknown"
    try:
        ps = f"(Get-AuthenticodeSignature -LiteralPath '{path}').Status"
        r = subprocess.run(["powershell", "-NoProfile", "-Command", ps], capture_output=True, timeout=6, creationflags=0x08000000)
        signature = (r.stdout or b"").decode("utf-8", errors="ignore").strip()
    except Exception:
        pass
    return {
        "path": path,
        "size": st.st_size,
        "mtime": st.st_mtime,
        "atime": st.st_atime,
        "ctime": st.st_ctime,
        "md5": _hash_file(path, "md5"),
        "sha1": _hash_file(path, "sha1"),
        "sha256": _hash_file(path, "sha256"),
        "signature": signature,
        "timestomp_suspected": st.st_mtime < st.st_ctime,
    }

