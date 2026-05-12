from __future__ import annotations

import hashlib


def hash_bytes(data: bytes) -> dict:
    return {
        "md5": hashlib.md5(data).hexdigest(),
        "sha1": hashlib.sha1(data).hexdigest(),
        "sha256": hashlib.sha256(data).hexdigest(),
    }


def hash_file(path: str) -> dict:
    with open(path, "rb") as f:
        data = f.read()
    return hash_bytes(data)


def imphash_placeholder(path: str) -> str:
    with open(path, "rb") as f:
        return hashlib.md5(f.read(4096)).hexdigest()

