from __future__ import annotations

import io
import json
import zipfile
from datetime import datetime


def build_user_export_zip(payloads: dict[str, list[dict]]) -> bytes:
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w", compression=zipfile.ZIP_DEFLATED) as zf:
        for name, rows in payloads.items():
            zf.writestr(f"{name}.json", json.dumps(rows, ensure_ascii=False, indent=2))
        zf.writestr("meta.json", json.dumps({"generated_at": datetime.utcnow().isoformat() + "Z"}, ensure_ascii=False))
    return buf.getvalue()
