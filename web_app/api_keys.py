from __future__ import annotations

import hashlib
import secrets
import string


def generate_api_key(prefix: str = "argus") -> str:
    alphabet = string.ascii_letters + string.digits
    token = "".join(secrets.choice(alphabet) for _ in range(32))
    return f"{prefix}_{token}"


def hash_api_key(plain: str) -> str:
    return hashlib.sha256((plain or "").encode("utf-8")).hexdigest()
