from __future__ import annotations

import json
from datetime import datetime, timezone


def export_to_json(scan_data: dict, pretty: bool = True) -> str:
    payload = {
        "metadata": {
            "exported_at": datetime.now(timezone.utc).isoformat(),
            "schema_version": "1.0",
            "source": "argus-scanner",
        },
        "scan": scan_data or {},
    }
    if pretty:
        return json.dumps(payload, ensure_ascii=False, indent=2)
    return json.dumps(payload, ensure_ascii=False, separators=(",", ":"))

