from __future__ import annotations


def export_to_csv_rows(scan_data: dict) -> list[dict]:
    rows = []
    for issue in (scan_data.get("issues_found") or []):
        if not isinstance(issue, dict):
            continue
        rows.append({
            "tipo": issue.get("tipo", ""),
            "nombre": issue.get("nombre", ""),
            "ruta": issue.get("ruta", ""),
            "archivo": issue.get("archivo", ""),
            "categoria": issue.get("categoria", ""),
            "alerta": issue.get("alerta", ""),
            "confidence": issue.get("confidence", ""),
        })
    return rows

