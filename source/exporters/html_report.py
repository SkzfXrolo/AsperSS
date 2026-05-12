from __future__ import annotations

from html import escape


def export_html_report(scan_data: dict) -> str:
    rows = []
    for i in (scan_data.get("issues_found") or []):
        if not isinstance(i, dict):
            continue
        rows.append(
            "<tr>"
            f"<td>{escape(str(i.get('tipo','')))}</td>"
            f"<td>{escape(str(i.get('nombre','')))}</td>"
            f"<td>{escape(str(i.get('ruta','')))}</td>"
            f"<td>{escape(str(i.get('alerta','')))}</td>"
            "</tr>"
        )
    return "<html><body><h1>Argus Report</h1><table border='1'><tr><th>Tipo</th><th>Nombre</th><th>Ruta</th><th>Alerta</th></tr>" + "".join(rows) + "</table></body></html>"

