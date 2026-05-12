from __future__ import annotations

import requests


def send_to_wazuh(scan_data: dict, wazuh_api_url: str, token: str) -> dict:
    headers = {"Authorization": f"Bearer {token}", "Content-Type": "application/json"}
    payload = {"argus_scan": scan_data}
    r = requests.post(f"{wazuh_api_url.rstrip('/')}/events", json=payload, headers=headers, timeout=15)
    return {"status_code": r.status_code, "ok": bool(r.ok), "text": r.text[:500]}

