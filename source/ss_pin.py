"""PIN de sesión SS (6 dígitos) sobre scan_token / license embebida — v1.8."""
from __future__ import annotations

import hashlib
import json
import os
import random
import time
from pathlib import Path
from typing import Any, Dict, Optional


PIN_TTL_SEC = 2 * 60 * 60  # 2 horas
STORE_NAME = "argus_ss_pin.json"


def _store_path() -> Path:
    base = os.environ.get("LOCALAPPDATA") or os.environ.get("APPDATA") or os.getcwd()
    d = Path(base) / "ArgusScanner"
    d.mkdir(parents=True, exist_ok=True)
    return d / STORE_NAME


def _hash_pin(pin: str, salt: str) -> str:
    return hashlib.sha256(f"{salt}:{pin}".encode("utf-8")).hexdigest()


def generate_pin(scan_token: str, staff_hint: str = "") -> Dict[str, Any]:
    """Genera PIN de 6 dígitos ligado al token. Devuelve dict público (sin hash)."""
    pin = f"{random.SystemRandom().randint(0, 999999):06d}"
    salt = hashlib.sha256(os.urandom(16)).hexdigest()[:16]
    now = int(time.time())
    rec = {
        "pin_hash": _hash_pin(pin, salt),
        "salt": salt,
        "token": (scan_token or "").strip(),
        "staff_hint": staff_hint or "",
        "created_at": now,
        "expires_at": now + PIN_TTL_SEC,
    }
    _store_path().write_text(json.dumps(rec), encoding="utf-8")
    return {
        "pin": pin,
        "expires_at": rec["expires_at"],
        "ttl_sec": PIN_TTL_SEC,
        "staff_hint": staff_hint,
    }


def validate_pin(pin: str) -> Optional[str]:
    """
    Valida PIN. Si ok, devuelve scan_token asociado.
    Si falla / expiró, None.
    """
    pin = (pin or "").strip()
    if len(pin) != 6 or not pin.isdigit():
        return None
    path = _store_path()
    if not path.is_file():
        return None
    try:
        rec = json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return None
    if int(time.time()) > int(rec.get("expires_at") or 0):
        return None
    salt = rec.get("salt") or ""
    if _hash_pin(pin, salt) != rec.get("pin_hash"):
        return None
    token = (rec.get("token") or "").strip()
    return token or None


def clear_pin() -> None:
    try:
        p = _store_path()
        if p.is_file():
            p.unlink()
    except Exception:
        pass


def peek_expiry() -> Optional[int]:
    path = _store_path()
    if not path.is_file():
        return None
    try:
        rec = json.loads(path.read_text(encoding="utf-8"))
        return int(rec.get("expires_at") or 0)
    except Exception:
        return None
