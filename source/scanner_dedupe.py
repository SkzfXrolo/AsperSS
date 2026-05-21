"""Elimina hallazgos duplicados antes de enviar al panel."""
from __future__ import annotations

import os
from typing import Any, Dict, List, Tuple


def _issue_key(issue: Dict[str, Any]) -> Tuple[str, str, str]:
    tipo = (issue.get("tipo") or "").lower()
    path = (issue.get("ruta") or issue.get("archivo") or "").lower()
    path = os.path.normcase(path) if path else ""
    nombre = (issue.get("nombre") or "")[:160].lower()
    return tipo, path, nombre


def dedupe_issues(issues: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    seen = set()
    out: List[Dict[str, Any]] = []
    removed = 0
    for item in issues or []:
        key = _issue_key(item)
        if key in seen:
            removed += 1
            continue
        seen.add(key)
        out.append(item)
    if removed:
        print(f"🧹 Dedupe: {removed} hallazgo(s) duplicado(s) eliminados")
    return out
