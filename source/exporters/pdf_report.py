from __future__ import annotations


def export_pdf_text(scan_data: dict) -> bytes:
    lines = ["Argus PDF-like Report", "=" * 30]
    for i in (scan_data.get("issues_found") or []):
        if isinstance(i, dict):
            lines.append(f"- {i.get('tipo','unknown')}: {i.get('nombre','')}")
    # Placeholder plaintext payload; caller may persist as .pdf.txt
    return "\n".join(lines).encode("utf-8", errors="ignore")

