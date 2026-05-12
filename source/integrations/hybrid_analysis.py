from __future__ import annotations

import requests


def submit_hybrid_analysis(file_hash: str, api_key: str):
    headers = {"api-key": api_key, "User-Agent": "Falcon Sandbox"}
    url = f"https://www.hybrid-analysis.com/api/v2/search/hash?hash={file_hash}"
    r = requests.get(url, headers=headers, timeout=20)
    return {"status_code": r.status_code, "ok": bool(r.ok), "text": r.text[:500]}

