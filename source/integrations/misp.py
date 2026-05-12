from __future__ import annotations

import requests


def submit_to_misp(scan_data: dict, misp_url: str, api_key: str) -> dict:
    event = {
        "Event": {
            "info": "Argus scanner event",
            "analysis": 1,
            "threat_level_id": 2,
            "Attribute": [],
        }
    }
    for issue in (scan_data.get("issues_found") or []):
        if not isinstance(issue, dict):
            continue
        event["Event"]["Attribute"].append({
            "type": "comment",
            "category": "External analysis",
            "value": f"{issue.get('tipo','unknown')} | {issue.get('nombre','')}",
        })
    headers = {"Authorization": api_key, "Accept": "application/json", "Content-Type": "application/json"}
    event["Event"]["info"] = f"Argus scanner event ({len(event['Event']['Attribute'])} findings)"
    r = requests.post(f"{misp_url.rstrip('/')}/events/add", json=event, headers=headers, timeout=20)
    return {"status_code": r.status_code, "ok": bool(r.ok), "text": r.text[:500]}

