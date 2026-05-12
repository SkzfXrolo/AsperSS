from __future__ import annotations


def export_markdown_report(scan_data: dict) -> str:
    lines = ["# Argus Report", ""]
    for i in (scan_data.get("issues_found") or []):
        if isinstance(i, dict):
            lines.append(f"- **{i.get('tipo','unknown')}**: {i.get('nombre','')} (`{i.get('ruta','')}`)")
    return "\n".join(lines)

