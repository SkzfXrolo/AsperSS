from __future__ import annotations

import requests


def send_heartbeat(base_url: str, agent_id: str):
    r = requests.post(f"{base_url.rstrip('/')}/api/heartbeat", json={"agent_id": agent_id}, timeout=10)
    return {"status_code": r.status_code, "ok": bool(r.ok)}

