from __future__ import annotations

import base64
import json
import os
import secrets
from datetime import datetime
from pathlib import Path

from cryptography.hazmat.primitives.ciphers.aead import AESGCM


def backups_dir() -> Path:
    p = Path(__file__).resolve().parent / "backups"
    p.mkdir(parents=True, exist_ok=True)
    return p


def encrypt_json_payload(payload: dict, password: str) -> dict:
    key = AESGCM.generate_key(bit_length=128)
    aes = AESGCM(key)
    nonce = secrets.token_bytes(12)
    plaintext = json.dumps(payload, ensure_ascii=False).encode("utf-8")
    ciphertext = aes.encrypt(nonce, plaintext, password.encode("utf-8"))
    return {
        "ts": datetime.utcnow().isoformat() + "Z",
        "nonce_b64": base64.b64encode(nonce).decode("ascii"),
        "key_b64": base64.b64encode(key).decode("ascii"),
        "ciphertext_b64": base64.b64encode(ciphertext).decode("ascii"),
    }


def save_backup(doc: dict) -> str:
    bid = datetime.utcnow().strftime("%Y%m%d%H%M%S") + "_" + secrets.token_hex(4)
    path = backups_dir() / f"{bid}.json"
    path.write_text(json.dumps(doc, ensure_ascii=False), encoding="utf-8")
    return bid


def list_backups() -> list[dict]:
    out = []
    for fp in sorted(backups_dir().glob("*.json"), reverse=True):
        st = fp.stat()
        out.append({
            "id": fp.stem,
            "filename": fp.name,
            "size": st.st_size,
            "mtime": datetime.utcfromtimestamp(st.st_mtime).isoformat() + "Z",
        })
    return out


def read_backup(backup_id: str) -> dict | None:
    fp = backups_dir() / f"{backup_id}.json"
    if not fp.exists():
        return None
    return json.loads(fp.read_text(encoding="utf-8"))


def rotate_backups(max_items: int = 30):
    files = sorted(backups_dir().glob("*.json"), key=lambda p: p.stat().st_mtime, reverse=True)
    for fp in files[max_items:]:
        try:
            fp.unlink()
        except Exception:
            pass
