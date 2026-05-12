from __future__ import annotations

import requests


def check_latest_version(current_version: str, endpoint: str):
    r = requests.get(endpoint, timeout=10)
    latest = (r.json() or {}).get("latest", current_version) if r.ok else current_version
    return {"current": current_version, "latest": latest, "update_available": latest != current_version}

