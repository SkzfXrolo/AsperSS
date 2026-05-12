from __future__ import annotations

import requests


def send_discord_webhook(webhook_url: str, findings: list[dict]):
    content = "\n".join([f"- {f.get('tipo','unknown')}: {f.get('nombre','')}" for f in findings[:20]])
    r = requests.post(webhook_url, json={"content": f"Argus findings:\n{content}"}, timeout=15)
    return {"status_code": r.status_code, "ok": bool(r.ok)}

