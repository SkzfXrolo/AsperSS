from __future__ import annotations

import hashlib
import hmac
import json
import time
from typing import Any

import requests


def sign_payload(secret: str, payload: dict[str, Any]) -> tuple[str, str]:
    body = json.dumps(payload, ensure_ascii=False, separators=(",", ":")).encode("utf-8")
    sig = hmac.new(secret.encode("utf-8"), body, hashlib.sha256).hexdigest()
    return body.decode("utf-8"), sig


def deliver_with_retries(url: str, secret: str, payload: dict[str, Any], attempts: int = 4) -> tuple[bool, int]:
    body, sig = sign_payload(secret, payload)
    waits = [60, 300, 900, 3600]
    last_status = 0
    for idx in range(max(1, attempts)):
        try:
            res = requests.post(
                url,
                data=body.encode("utf-8"),
                headers={
                    "Content-Type": "application/json",
                    "X-Argus-Signature": f"sha256={sig}",
                },
                timeout=8,
            )
            last_status = int(res.status_code or 0)
            if 200 <= last_status < 300:
                return True, last_status
        except Exception:
            last_status = 0
        if idx < len(waits):
            time.sleep(waits[idx])
    return False, last_status
