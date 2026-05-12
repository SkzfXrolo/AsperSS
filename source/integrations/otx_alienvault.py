from __future__ import annotations

import requests


def check_otx_ioc(ioc: str, api_key: str):
    headers = {"X-OTX-API-KEY": api_key}
    r = requests.get(f"https://otx.alienvault.com/api/v1/indicators/IPv4/{ioc}/general", headers=headers, timeout=20)
    return {"status_code": r.status_code, "ok": bool(r.ok), "json": r.json() if r.ok else {}}

