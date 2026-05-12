from __future__ import annotations

import os
import time
import requests

from utils.cache import LRUCache


_CACHE = LRUCache(max_size=512)
_LAST_REQ = 0.0


def _throttle():
    global _LAST_REQ
    wait = 15 - (time.time() - _LAST_REQ)
    if wait > 0:
        time.sleep(wait)
    _LAST_REQ = time.time()


def _vt_get(path):
    key = os.environ.get("VT_API_KEY")
    if not key:
        return {"error": "VT_API_KEY not set"}
    cache_key = f"vt:{path}"
    c = _CACHE.get(cache_key)
    if c is not None:
        return c
    _throttle()
    headers = {"x-apikey": key}
    r = requests.get(f"https://www.virustotal.com/api/v3/{path}", headers=headers, timeout=20)
    payload = {"status_code": r.status_code, "data": r.json() if r.headers.get("content-type", "").startswith("application/json") else {}}
    _CACHE.set(cache_key, payload)
    return payload


def check_hash_vt(file_hash):
    out = _vt_get(f"files/{file_hash}")
    stats = (((out.get("data") or {}).get("data") or {}).get("attributes") or {}).get("last_analysis_stats", {})
    first_seen = (((out.get("data") or {}).get("data") or {}).get("attributes") or {}).get("first_submission_date")
    return {"malicious": stats.get("malicious", 0), "suspicious": stats.get("suspicious", 0), "first_seen": first_seen}


def check_ip_vt(ip):
    out = _vt_get(f"ip_addresses/{ip}")
    rep = (((out.get("data") or {}).get("data") or {}).get("attributes") or {}).get("reputation", 0)
    return {"reputation": rep}

