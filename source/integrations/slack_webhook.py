from __future__ import annotations

import requests


def send_slack_webhook(webhook_url: str, findings: list[dict]):
    lines = [f"*{f.get('tipo','unknown')}* {f.get('nombre','')}" for f in findings[:20]]
    r = requests.post(webhook_url, json={"text": "Argus findings\n" + "\n".join(lines)}, timeout=15)
    return {"status_code": r.status_code, "ok": bool(r.ok)}

