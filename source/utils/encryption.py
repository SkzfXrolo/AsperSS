from __future__ import annotations

import base64
import json
import os

from cryptography.hazmat.primitives.ciphers.aead import AESGCM
from cryptography.hazmat.primitives.kdf.pbkdf2 import PBKDF2HMAC
from cryptography.hazmat.primitives import hashes


def _derive_key(password: str, salt: bytes) -> bytes:
    kdf = PBKDF2HMAC(
        algorithm=hashes.SHA256(),
        length=32,
        salt=salt,
        iterations=100000,
    )
    return kdf.derive(password.encode("utf-8"))


def encrypt_scan_result(data: dict, password: str) -> bytes:
    payload = json.dumps(data, ensure_ascii=False).encode("utf-8")
    salt = os.urandom(16)
    nonce = os.urandom(12)
    key = _derive_key(password, salt)
    cipher = AESGCM(key)
    ct = cipher.encrypt(nonce, payload, None)
    return base64.b64encode(salt + nonce + ct)


def decrypt_scan_result(encrypted: bytes, password: str) -> dict:
    raw = base64.b64decode(encrypted)
    salt, nonce, ct = raw[:16], raw[16:28], raw[28:]
    key = _derive_key(password, salt)
    cipher = AESGCM(key)
    pt = cipher.decrypt(nonce, ct, None)
    return json.loads(pt.decode("utf-8"))

