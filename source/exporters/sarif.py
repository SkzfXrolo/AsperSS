from __future__ import annotations


def export_sarif(scan_data: dict) -> dict:
    results = []
    for issue in (scan_data.get("issues_found") or []):
        if not isinstance(issue, dict):
            continue
        results.append(
            {
                "ruleId": str(issue.get("tipo", "argus.finding")),
                "level": "error" if str(issue.get("alerta", "")).upper() == "CRITICAL" else "warning",
                "message": {"text": str(issue.get("nombre", ""))},
                "locations": [{"physicalLocation": {"artifactLocation": {"uri": str(issue.get("ruta", ""))}}}],
            }
        )
    return {"version": "2.1.0", "runs": [{"tool": {"driver": {"name": "argus-scanner"}}, "results": results}]}

