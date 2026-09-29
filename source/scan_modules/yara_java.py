"""YARA sobre JARs y rutas Java — fase Paranoid del ScanPipeline (v1.8)."""
from __future__ import annotations

import os
from pathlib import Path
from typing import Any, List


def _issue(nombre, ruta, rule, conf=0.85):
    return {
        "nombre": nombre,
        "ruta": os.path.dirname(ruta) if ruta else "",
        "archivo": ruta or "",
        "tipo": "yara_java",
        "categoria": "YARA",
        "alerta": "CRITICAL" if conf >= 0.85 else "SOSPECHOSO",
        "confidence": conf,
        "detected_patterns": [f"yara:{rule}"],
        "explicacion": (
            f"Regla YARA '{rule}' coincidió en un JAR/binario Java. "
            "Indica firma conocida de cheat/injector/bypass."
        ),
    }


def _candidate_paths(app: Any) -> List[str]:
    paths: List[str] = []
    appdata = os.environ.get("APPDATA", "")
    local = os.environ.get("LOCALAPPDATA", "")
    user = os.environ.get("USERPROFILE", "")
    roots = [
        os.path.join(appdata, ".minecraft"),
        os.path.join(appdata, "Roaming", ".minecraft"),
        os.path.join(appdata, "lunarclient"),
        os.path.join(local, "Packages"),
        os.path.join(user, "Downloads"),
        os.path.join(user, "Desktop"),
    ]
    # JARs recientes ya tocados por el scan
    for iss in getattr(app, "issues_found", []) or []:
        for key in ("archivo", "ruta"):
            p = iss.get(key) or ""
            if p.lower().endswith(".jar") and os.path.isfile(p):
                paths.append(p)

    for root in roots:
        if not os.path.isdir(root):
            continue
        try:
            for dirpath, dirnames, filenames in os.walk(root):
                # Limitar profundidad
                depth = dirpath[len(root) :].count(os.sep)
                if depth > 4:
                    dirnames[:] = []
                    continue
                for name in filenames:
                    if name.lower().endswith(".jar"):
                        paths.append(os.path.join(dirpath, name))
                if len(paths) > 80:
                    break
        except OSError:
            continue
        if len(paths) > 80:
            break

    # Dedup preserve order
    seen = set()
    out = []
    for p in paths:
        if p not in seen and os.path.isfile(p):
            seen.add(p)
            out.append(p)
    return out[:60]


def scan_java_yara(app: Any) -> List[dict]:
    try:
        from utils.yara_scan import scan_with_yara_rules, DEFAULT_RULES_DIR
    except Exception:
        try:
            from yara_scan import scan_with_yara_rules, DEFAULT_RULES_DIR  # type: ignore
        except Exception as e:
            print(f"[yara_java] yara_scan no disponible: {e}")
            return []

    rules_dir = DEFAULT_RULES_DIR
    if not Path(rules_dir).exists():
        # Fallback: reglas mínimas embebidas vía archivo suelto
        alt = Path(__file__).resolve().parents[1] / "yara_rules"
        rules_dir = alt if alt.exists() else rules_dir

    findings = []
    for path in _candidate_paths(app):
        try:
            matches = scan_with_yara_rules(path, rules_dir) or []
        except Exception:
            continue
        for m in matches:
            rule = getattr(m, "rule", None) or str(m)
            findings.append(
                _issue(f"YARA match: {rule}", path, rule, conf=0.88)
            )
        if len(findings) >= 25:
            break
    return findings
