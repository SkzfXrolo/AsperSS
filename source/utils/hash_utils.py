from __future__ import annotations

import hashlib
import os
from typing import Optional


def hash_bytes(data: bytes) -> dict:
    return {
        "md5": hashlib.md5(data).hexdigest(),
        "sha1": hashlib.sha1(data).hexdigest(),
        "sha256": hashlib.sha256(data).hexdigest(),
    }


def sha256_file(path: str, max_bytes: Optional[int] = None, chunk_size: int = 65536) -> Optional[str]:
    """SHA256 por bloques; opcionalmente solo los primeros max_bytes."""
    try:
        h = hashlib.sha256()
        read = 0
        with open(path, "rb") as f:
            while True:
                if max_bytes is not None:
                    to_read = min(chunk_size, max_bytes - read)
                    if to_read <= 0:
                        break
                else:
                    to_read = chunk_size
                block = f.read(to_read)
                if not block:
                    break
                h.update(block)
                read += len(block)
        return h.hexdigest()
    except OSError:
        return None


def hash_file(path: str) -> dict:
    digest = sha256_file(path)
    if digest is None:
        raise OSError(f"No se pudo hashear: {path}")
    return {"sha256": digest}


def file_fingerprint(path: str) -> Optional[tuple[int, float]]:
    """(size, mtime) para lookup rápido sin leer contenido."""
    try:
        st = os.stat(path)
        return st.st_size, st.st_mtime
    except OSError:
        return None


def imphash_placeholder(path: str) -> str:
    digest = sha256_file(path, max_bytes=4096)
    return digest or hashlib.md5(b"").hexdigest()
