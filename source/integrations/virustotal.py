from __future__ import annotations

import os
import time
import requests

from utils.cache import LRUCache

_CACHE = LRUCache(max_size=512)
_LAST = 0.0


def _rate_limit():
    global _LAST
    wait = 15 - (time.time() - _LAST)
    if wait > 0:
        time.sleep(wait)
    _LAST = time.time()


def _get(path: str):
    key = os.environ.get("VT_API_KEY")
    if not key:
        return {"error": "VT_API_KEY missing"}
    ck = f"vt:{path}"
    cached = _CACHE.get(ck)
    if cached is not None:
        return cached
    _rate_limit()
    r = requests.get(f"https://www.virustotal.com/api/v3/{path}", headers={"x-apikey": key}, timeout=20)
    out = {"status_code": r.status_code, "json": r.json() if "json" in r.headers.get("content-type", "") else {}}
    _CACHE.set(ck, out)
    return out


def vt_check_hash(file_hash: str):
    return _get(f"files/{file_hash}")


def vt_check_ip(ip: str):
    return _get(f"ip_addresses/{ip}")

