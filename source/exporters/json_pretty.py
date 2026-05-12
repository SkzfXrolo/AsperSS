from __future__ import annotations

import json
from datetime import datetime, timezone


def export_json_pretty(scan_data: dict) -> str:
    payload = {
        "metadata": {"exported_at": datetime.now(timezone.utc).isoformat(), "source": "argus", "schema": "2.0"},
        "scan": scan_data or {},
    }
    return json.dumps(payload, ensure_ascii=False, indent=2)

