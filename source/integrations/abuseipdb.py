from __future__ import annotations

import requests


def check_ip_abuse(ip: str, api_key: str):
    headers = {"Key": api_key, "Accept": "application/json"}
    r = requests.get("https://api.abuseipdb.com/api/v2/check", params={"ipAddress": ip, "maxAgeInDays": 90}, headers=headers, timeout=20)
    return {"status_code": r.status_code, "ok": bool(r.ok), "json": r.json() if r.ok else {}}

