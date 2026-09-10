"""Enriquecimiento de hallazgos para staff — hash, timestamps, evidencia relacionada (v1.8+)."""
from __future__ import annotations

import os
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional


def _iso_from_epoch(ts: Optional[float]) -> str:
    if ts is None:
        return ""
    try:
        return datetime.fromtimestamp(float(ts), tz=timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    except Exception:
        return ""


def _resolve_file_path(issue: dict) -> str:
    for key in ("archivo", "ruta"):
        p = issue.get(key) or ""
        if isinstance(p, str) and p and os.path.isfile(p):
            return p
    # Prefetch: ruta suele ser el .pf completo
    ruta = issue.get("ruta") or ""
    archivo = issue.get("archivo") or ""
    if ruta and archivo and not os.path.isabs(archivo):
        cand = os.path.join(ruta, archivo) if os.path.isdir(ruta) else ruta
        if os.path.isfile(cand):
            return cand
    return ""


def _normalize_confidence(issue: dict) -> None:
    c = issue.get("confidence")
    if c is None:
        return
    try:
        c = float(c)
    except (TypeError, ValueError):
        return
    # Unificar a 0–1 (si viene 0–100)
    if c > 1.0:
        c = min(1.0, c / 100.0)
    issue["confidence"] = round(max(0.0, min(1.0, c)), 4)


def _attach_file_meta(issue: dict, path: str, app: Any = None) -> None:
    try:
        st = os.stat(path)
    except OSError:
        return
    issue.setdefault("size", st.st_size)
    issue.setdefault("mtime", st.st_mtime)
    if not issue.get("timestamp"):
        issue["timestamp"] = _iso_from_epoch(st.st_mtime)
    if not issue.get("last_executed") and issue.get("tipo") in (
        "prefetch_hack",
        "amcache_hack_execution",
        "bam_execution",
        "bam_suspicious",
        "registry_userassist_hack",
        "usn_deleted_hack",
    ):
        issue["last_executed"] = issue["timestamp"]

    # Normalizar hash alternativo
    if issue.get("hash") and not issue.get("file_hash"):
        issue["file_hash"] = issue["hash"]

    sha = issue.get("file_hash") or issue.get("sha256") or ""
    if not sha and app is not None and hasattr(app, "_cached_sha256"):
        try:
            sha = app._cached_sha256(path, max_bytes=8 * 1024 * 1024) or ""
        except Exception:
            sha = ""
    if not sha:
        try:
            import hashlib
            h = hashlib.sha256()
            with open(path, "rb") as f:
                for chunk in iter(lambda: f.read(65536), b""):
                    h.update(chunk)
                    if f.tell() > 8 * 1024 * 1024:
                        break
            sha = h.hexdigest()
        except Exception:
            sha = ""
    if sha:
        issue["file_hash"] = sha
        issue["sha256"] = sha

    # Authenticode: solo Paranoid o SOSPECHOSO+/CRITICAL en .exe
    mode = ""
    try:
        mode = str(
            getattr(app, "scan_mode", None)
            or (getattr(app, "config", {}) or {}).get("scan_mode")
            or ""
        ).lower()
    except Exception:
        mode = ""
    alerta = (issue.get("alerta") or "").upper()
    want_sig = mode in ("paranoid", "deep") or alerta in ("CRITICAL", "SOSPECHOSO")
    if want_sig and path.lower().endswith(".exe") and not issue.get("signature"):
        try:
            from utils.file_metadata import get_file_metadata
            meta = get_file_metadata(path)
            if meta.get("signature"):
                issue["signature"] = meta["signature"]
                extra = issue.get("extra") if isinstance(issue.get("extra"), dict) else {}
                extra = dict(extra)
                extra["signature"] = meta["signature"]
                issue["extra"] = extra
        except Exception:
            pass


def _stem_from_issue(issue: dict) -> str:
    for pat in issue.get("detected_patterns") or []:
        s = str(pat)
        for prefix in ("prefetch:", "temporal_correlation:", "usn:", "bam:", "yara:"):
            if s.startswith(prefix):
                return s.split(":", 1)[1].split(",")[0].strip().lower()
    blob = (issue.get("nombre") or "") + " " + (issue.get("archivo") or "")
    blob = blob.lower()
    for stem in (
        "vape", "entropy", "whiteout", "liquidbounce", "wurst", "meteor",
        "rusherhack", "aristois", "sigma", "flux", "rise", "astolfo",
        "thunderhack", "doomsday", "raven", "myau", "drip", "konas",
        "tenacity", "phobos", "salhack", "inertia", "azura", "weave",
    ):
        if stem in blob:
            return stem
    return ""


def _cross_link_related(issues: List[dict]) -> None:
    """Adjunta related_paths / related_tipos por stem de hack (evidencia cruzada)."""
    by_stem: Dict[str, List[dict]] = {}
    for iss in issues:
        stem = _stem_from_issue(iss)
        if not stem:
            continue
        by_stem.setdefault(stem, []).append(iss)

    for stem, group in by_stem.items():
        if len(group) < 2:
            continue
        paths = []
        tipos = []
        for g in group:
            p = g.get("archivo") or g.get("ruta") or ""
            if p and p not in paths:
                paths.append(p)
            t = g.get("tipo") or ""
            if t and t not in tipos:
                tipos.append(t)
        for g in group:
            extra = g.get("extra") if isinstance(g.get("extra"), dict) else {}
            extra = dict(extra)
            extra["related_stem"] = stem
            extra["related_paths"] = paths[:12]
            extra["related_tipos"] = tipos[:12]
            extra["related_count"] = len(group)
            g["extra"] = extra
            pats = list(g.get("detected_patterns") or [])
            tag = f"related:{stem}:{len(group)}"
            if tag not in pats:
                pats.append(tag)
            g["detected_patterns"] = pats


def enrich_issues(issues: List[dict], app: Any = None) -> List[dict]:
    """
    Normaliza confidence, adjunta hash/mtime/timestamp y cruza evidencias.
    No elimina hallazgos — solo añade contexto para staff/panel.
    """
    if not issues:
        return issues

    for issue in issues:
        if not isinstance(issue, dict):
            continue
        _normalize_confidence(issue)
        path = _resolve_file_path(issue)
        if path:
            _attach_file_meta(issue, path, app=app)
        # Persistir combo penalty en extra (panel/API)
        combo = issue.get("combination_penalty")
        if combo:
            extra = issue.get("extra") if isinstance(issue.get("extra"), dict) else {}
            extra = dict(extra)
            extra["combination_penalty"] = combo
            issue["extra"] = extra
        # Asegurar explicacion mínima
        if not issue.get("explicacion"):
            nombre = issue.get("nombre") or "Hallazgo"
            tipo = issue.get("tipo") or "unknown"
            issue["explicacion"] = (
                f"{nombre} (tipo={tipo}). Revisar ruta, hash y patrones detectados."
            )

    _cross_link_related(issues)
    return issues
