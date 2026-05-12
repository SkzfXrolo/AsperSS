from __future__ import annotations

import csv
import io


def export_csv_findings(scan_data: dict) -> str:
    buf = io.StringIO()
    w = csv.DictWriter(buf, fieldnames=["tipo", "nombre", "ruta", "archivo", "categoria", "alerta", "confidence"])
    w.writeheader()
    for issue in (scan_data.get("issues_found") or []):
        if isinstance(issue, dict):
            w.writerow({k: issue.get(k, "") for k in w.fieldnames})
    return buf.getvalue()

