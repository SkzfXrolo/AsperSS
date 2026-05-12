from __future__ import annotations

import requests


def send_to_splunk_hec(scan_data: dict, hec_url: str, hec_token: str, source: str = "argus_scanner") -> dict:
    headers = {"Authorization": f"Splunk {hec_token}"}
    payload = {"event": scan_data, "sourcetype": "_json", "source": source}
    r = requests.post(hec_url, json=payload, headers=headers, timeout=15)
    return {"status_code": r.status_code, "ok": bool(r.ok), "text": r.text[:500]}

