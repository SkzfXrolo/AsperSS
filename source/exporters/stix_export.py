from __future__ import annotations

from datetime import datetime, timezone
import uuid


def export_to_stix(scan_data: dict) -> dict:
    """Convierte resultados del scanner a STIX 2.1 bundle básico."""
    objects = []
    now = datetime.now(timezone.utc).isoformat()
    for issue in (scan_data.get("issues_found") or []):
        if not isinstance(issue, dict):
            continue
        name = str(issue.get("nombre", "Argus finding"))
        pattern = f"[x-argus-finding:value = '{str(issue.get('tipo', 'unknown'))}']"
        indicator_id = f"indicator--{uuid.uuid4()}"
        objects.append({
            "type": "indicator",
            "spec_version": "2.1",
            "id": indicator_id,
            "created": now,
            "modified": now,
            "name": name[:200],
            "description": str(issue.get("explicacion", ""))[:1000],
            "pattern_type": "stix",
            "pattern": pattern,
            "valid_from": now,
            "labels": ["argus-scan", str(issue.get("categoria", "unknown")).lower()],
            "confidence": int(float(issue.get("confidence", 0.5)) * 100),
        })
    return {
        "type": "bundle",
        "id": f"bundle--{uuid.uuid4()}",
        "objects": objects,
    }

