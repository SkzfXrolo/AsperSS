"""Caché en memoria de hashes SHA256 para evitar releer el mismo archivo."""
from __future__ import annotations

import os
from typing import Dict, Optional, Tuple

try:
    from utils.hash_utils import sha256_file
except ImportError:
    from hash_utils import sha256_file  # type: ignore


class FileHashCache:
    _store: Dict[Tuple[str, Optional[int]], str] = {}

    @classmethod
    def sha256(cls, path: str, max_bytes: Optional[int] = None) -> Optional[str]:
        if not path or not os.path.isfile(path):
            return None
        key = (os.path.normcase(os.path.abspath(path)), max_bytes)
        if key in cls._store:
            return cls._store[key]
        digest = sha256_file(path, max_bytes=max_bytes)
        if digest:
            cls._store[key] = digest
        return digest

    @classmethod
    def clear(cls):
        cls._store.clear()
