from __future__ import annotations

from datetime import datetime, timezone
import uuid


def export_stix_bundle(scan_data: dict) -> dict:
    now = datetime.now(timezone.utc).isoformat()
    objects = []
    for issue in (scan_data.get("issues_found") or []):
        if not isinstance(issue, dict):
            continue
        objects.append(
            {
                "type": "indicator",
                "spec_version": "2.1",
                "id": f"indicator--{uuid.uuid4()}",
                "created": now,
                "modified": now,
                "name": str(issue.get("nombre", "Argus finding"))[:200],
                "pattern_type": "stix",
                "pattern": f"[x-argus-finding:value = '{str(issue.get('tipo','unknown'))}']",
                "valid_from": now,
            }
        )
    return {"type": "bundle", "id": f"bundle--{uuid.uuid4()}", "objects": objects}

