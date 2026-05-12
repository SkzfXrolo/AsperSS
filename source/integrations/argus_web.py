from __future__ import annotations

import requests


def send_scan_to_argus_web(base_url: str, scan_payload: dict, token: str | None = None):
    headers = {"Content-Type": "application/json"}
    if token:
        headers["Authorization"] = f"Bearer {token}"
    r = requests.post(f"{base_url.rstrip('/')}/api/scans", json=scan_payload, headers=headers, timeout=20)
    return {"status_code": r.status_code, "ok": bool(r.ok), "text": r.text[:500]}

