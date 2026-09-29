"""Checks P1 de alto valor aún no cableados / gaps — SS Mes 1–2."""
from __future__ import annotations

import os
import winreg
from typing import Any, List


def _issue(**kwargs):
    base = {
        "categoria": "FORENSE",
        "alerta": "SOSPECHOSO",
        "confidence": 0.8,
        "detected_patterns": [],
    }
    base.update(kwargs)
    return base


def load_signature_catalog() -> dict:
    try:
        from bundle_runtime import resolve_signature_file
        import json
        path = resolve_signature_file("catalog.json")
        # también bundle/signatures/catalog.json
        if not path:
            from bundle_runtime import bundle_path
            cand = bundle_path("signatures", "catalog.json")
            path = cand if os.path.isfile(cand) else None
        if not path:
            alt = os.path.join(
                os.path.dirname(__file__), "..", "bundle", "signatures", "catalog.json"
            )
            path = alt if os.path.isfile(alt) else None
        if path and os.path.isfile(path):
            with open(path, "r", encoding="utf-8") as f:
                return json.load(f) or {}
    except Exception:
        pass
    return {}


def scan_ghost_registry_extended(app: Any) -> List[dict]:
    """Amplía claves HKCU/HKLM Software\\* de ghost clients vía catálogo."""
    cat = load_signature_catalog()
    keys = list(cat.get("ghost_registry_keys") or [])
    if not keys:
        keys = [
            r"Software\Vape",
            r"Software\Entropy",
            r"Software\Whiteout",
            r"Software\Aristois",
            r"Software\Tenacity",
            r"Software\Konas",
            r"Software\Wurst",
            r"Software\Impact",
            r"Software\Salhack",
            r"Software\Inertia",
            r"Software\Phobos",
        ]
    out = []
    seen = set()
    for hive, hive_name in (
        (winreg.HKEY_CURRENT_USER, "HKCU"),
        (winreg.HKEY_LOCAL_MACHINE, "HKLM"),
    ):
        for sub in keys:
            try:
                with winreg.OpenKey(hive, sub):
                    key_name = sub.split("\\")[-1]
                    tag = f"{hive_name}\\{sub}"
                    if tag in seen:
                        continue
                    seen.add(tag)
                    out.append(
                        _issue(
                            nombre=f"Clave de registro ghost client: {key_name}",
                            ruta=tag,
                            archivo=key_name,
                            tipo="ghost_client_registry",
                            categoria="GHOST_CLIENT",
                            alerta="CRITICAL",
                            confidence=0.93,
                            detected_patterns=[f"registry:{key_name.lower().replace(' ', '_')}"],
                            explicacion=(
                                f"El registro {tag} suele quedar tras instalar/ejecutar "
                                f"un ghost client ({key_name})."
                            ),
                        )
                    )
            except FileNotFoundError:
                continue
            except OSError:
                continue
    return out


def scan_recycle_hack_names(app: Any) -> List[dict]:
    """Nombres de hacks en $Recycle.Bin (filename match boundary) + hash offline."""
    try:
        from forensic_match import match_hack_stem
    except Exception:
        return []
    known = {
        str(h).lower()
        for h in (getattr(app, "known_hack_hashes", None) or set())
        if h
    }
    out = []
    roots = []
    for letter in "CDEFGHIJ":
        p = f"{letter}:\\$Recycle.Bin"
        if os.path.isdir(p):
            roots.append(p)
    for root in roots:
        try:
            for dirpath, dirnames, filenames in os.walk(root):
                depth = dirpath[len(root) :].count(os.sep)
                if depth > 3:
                    dirnames[:] = []
                    continue
                for name in filenames:
                    full = os.path.join(dirpath, name)
                    stem = match_hack_stem(name)
                    hash_hit = False
                    file_sha = ""
                    # $R* = contenido real; hashear si hay catálogo
                    if (
                        known
                        and name.upper().startswith("$R")
                        and name.lower().endswith((".exe", ".jar", ".dll"))
                    ):
                        try:
                            if hasattr(app, "_cached_sha256"):
                                file_sha = app._cached_sha256(full) or ""
                            if file_sha and file_sha.lower() in known:
                                hash_hit = True
                        except Exception:
                            pass
                    if not stem and not hash_hit:
                        continue
                    try:
                        mtime = os.path.getmtime(full)
                        from datetime import datetime
                        ts = datetime.fromtimestamp(mtime).strftime("%Y-%m-%dT%H:%M:%S")
                    except Exception:
                        ts = ""
                    out.append(
                        _issue(
                            nombre=(
                                f"Papelera hash-match: {name}"
                                if hash_hit
                                else f"Hack en Papelera: {name}"
                            ),
                            ruta=full,
                            archivo=name,
                            tipo="recycle_hash_match" if hash_hit else "recycle_hack",
                            categoria="FORENSE",
                            alerta="CRITICAL",
                            confidence=0.96 if hash_hit else 0.9,
                            timestamp=ts,
                            last_executed=ts,
                            file_hash=file_sha[:64] if file_sha else "",
                            sha256=file_sha[:64] if file_sha else "",
                            detected_patterns=(
                                ["recycle_hash_catalog"]
                                if hash_hit
                                else [f"recycle:{stem}"]
                            ),
                            explicacion=(
                                "SHA256 en Papelera coincide con catálogo offline de hacks."
                                if hash_hit
                                else (
                                    f"Archivo en Recycle Bin con stem '{stem}'. "
                                    "Sugiere borrado pre-SS."
                                )
                            ),
                        )
                    )
                    if len(out) >= 15:
                        return out
        except OSError:
            continue
    return out


def scan_desktop_launchers(app: Any) -> List[dict]:
    """Scripts .bat/.ps1/.vbs en Desktop/Downloads con stems de hack."""
    try:
        from forensic_match import match_hack_stem
    except Exception:
        return []
    home = os.path.expanduser("~")
    roots = [
        os.path.join(home, "Desktop"),
        os.path.join(home, "Downloads"),
        os.path.join(os.environ.get("USERPROFILE", ""), "Desktop"),
        os.path.join(os.environ.get("USERPROFILE", ""), "Downloads"),
    ]
    out = []
    seen = set()
    for root in roots:
        if not os.path.isdir(root):
            continue
        try:
            for name in os.listdir(root):
                low = name.lower()
                if not low.endswith((".bat", ".ps1", ".vbs", ".cmd", ".lnk")):
                    continue
                stem = match_hack_stem(low)
                if not stem:
                    continue
                full = os.path.join(root, name)
                if full in seen:
                    continue
                seen.add(full)
                try:
                    mtime = os.path.getmtime(full)
                    from datetime import datetime
                    ts = datetime.fromtimestamp(mtime).strftime("%Y-%m-%dT%H:%M:%S")
                except Exception:
                    ts = ""
                out.append(
                    _issue(
                        nombre=f"Launcher sospechoso: {name}",
                        ruta=root,
                        archivo=full,
                        tipo="hack_launcher_script",
                        categoria="HACKS",
                        alerta="CRITICAL",
                        confidence=0.88,
                        timestamp=ts,
                        detected_patterns=[f"launcher:{stem}"],
                        explicacion=f"Script/atajo en {root} con stem '{stem}'.",
                    )
                )
        except OSError:
            continue
    return out


def scan_startup_hack_launchers(app: Any) -> List[dict]:
    """Startup folder + Run key names con stems de hack."""
    try:
        from forensic_match import match_hack_stem
    except Exception:
        return []
    out: List[dict] = []
    startup_dirs = []
    appdata = os.environ.get("APPDATA", "")
    progdata = os.environ.get("PROGRAMDATA", "")
    if appdata:
        startup_dirs.append(
            os.path.join(appdata, "Microsoft", "Windows", "Start Menu", "Programs", "Startup")
        )
    if progdata:
        startup_dirs.append(
            os.path.join(progdata, "Microsoft", "Windows", "Start Menu", "Programs", "Startup")
        )
    for root in startup_dirs:
        if not os.path.isdir(root):
            continue
        try:
            for name in os.listdir(root):
                stem = match_hack_stem(name)
                if not stem:
                    continue
                full = os.path.join(root, name)
                out.append(
                    _issue(
                        nombre=f"Startup sospechoso: {name}",
                        ruta=root,
                        archivo=full,
                        tipo="startup_hack_launcher",
                        categoria="PERSISTENCE",
                        alerta="CRITICAL",
                        confidence=0.9,
                        detected_patterns=[f"startup:{stem}"],
                        explicacion=f"Entrada en Startup con stem '{stem}'.",
                    )
                )
        except OSError:
            continue
    # HKCU Run values
    try:
        with winreg.OpenKey(
            winreg.HKEY_CURRENT_USER,
            r"Software\Microsoft\Windows\CurrentVersion\Run",
        ) as k:
            i = 0
            while True:
                try:
                    name, value, _ = winreg.EnumValue(k, i)
                    i += 1
                except OSError:
                    break
                blob = f"{name} {value}".lower()
                stem = match_hack_stem(blob)
                if not stem:
                    continue
                out.append(
                    _issue(
                        nombre=f"Run key sospechosa: {name}",
                        ruta=r"HKCU\Software\Microsoft\Windows\CurrentVersion\Run",
                        archivo=str(value)[:255],
                        tipo="startup_hack_launcher",
                        categoria="PERSISTENCE",
                        alerta="CRITICAL",
                        confidence=0.92,
                        detected_patterns=[f"run:{stem}"],
                        explicacion=f"Clave Run '{name}' con stem '{stem}'.",
                    )
                )
    except OSError:
        pass
    return out


def scan_ghost_configs_from_catalog(app: Any) -> List[dict]:
    """Rutas residuales extra desde catalog.json (hot-reload sin rebuild)."""
    cat = load_signature_catalog()
    rel_paths = list(cat.get("ghost_config_paths") or [])
    if not rel_paths:
        return []
    appdata = os.environ.get("APPDATA", "")
    localapp = os.environ.get("LOCALAPPDATA", "")
    home = os.path.expanduser("~")
    roots = {
        "%APPDATA%": appdata,
        "%LOCALAPPDATA%": localapp,
        "%USERPROFILE%": home,
        "~": home,
    }
    # Evitar duplicar lo que ya reportó scan_ghost_client_configs
    already = set()
    try:
        for iss in getattr(app, "issues_found", []) or []:
            if (iss.get("tipo") or "") == "ghost_client_config":
                already.add(os.path.normpath(str(iss.get("ruta") or "")).lower())
    except Exception:
        pass
    out: List[dict] = []
    for entry in rel_paths:
        if isinstance(entry, dict):
            label = entry.get("name") or entry.get("label") or "Ghost config"
            rel = entry.get("path") or ""
        else:
            label, rel = "Ghost config", str(entry)
        if not rel:
            continue
        resolved = rel
        for token, base in roots.items():
            if token in resolved:
                resolved = resolved.replace(token, base)
        if resolved.startswith(".\\") or (not os.path.isabs(resolved) and not resolved[1:2] == ":"):
            # relativo a APPDATA por defecto
            resolved = os.path.join(appdata, rel.lstrip("\\/"))
        resolved = os.path.normpath(resolved)
        if resolved.lower() in already:
            continue
        if not os.path.exists(resolved):
            continue
        try:
            from datetime import datetime
            ts = datetime.fromtimestamp(os.path.getmtime(resolved)).strftime("%Y-%m-%dT%H:%M:%S")
        except Exception:
            ts = ""
        already.add(resolved.lower())
        out.append(
            _issue(
                nombre=f"Config ghost (catálogo): {label}",
                ruta=resolved,
                archivo=os.path.basename(resolved),
                tipo="ghost_client_config",
                categoria="GHOST_CLIENT",
                alerta="CRITICAL",
                confidence=0.95,
                timestamp=ts,
                detected_patterns=[f"catalog_config:{label.lower().replace(' ', '_')}"],
                explicacion=f"Ruta del catálogo de firmas apunta a residual de {label}.",
            )
        )
    return out


def scan_temp_hack_named_exes(app: Any) -> List[dict]:
    """%TEMP% / Downloads: .exe con stem de hack (última 48h)."""
    try:
        from forensic_match import match_hack_stem, iso_from_epoch
    except Exception:
        return []
    import time
    cutoff = time.time() - 172800
    home = os.environ.get("USERPROFILE") or os.path.expanduser("~")
    roots = [
        os.environ.get("TEMP", ""),
        os.environ.get("TMP", ""),
        os.path.join(os.environ.get("LOCALAPPDATA", ""), "Temp"),
        os.path.join(home, "Downloads"),
        os.path.join(home, "Desktop"),
        os.path.join(home, "Documents"),
        r"C:\Users\Public\Downloads",
        r"C:\Users\Public\Desktop",
    ]
    out: List[dict] = []
    seen = set()
    for root in roots:
        if not root or not os.path.isdir(root):
            continue
        try:
            for name in os.listdir(root):
                if not name.lower().endswith((".exe", ".jar", ".dll")):
                    continue
                stem = match_hack_stem(name)
                if not stem:
                    continue
                full = os.path.join(root, name)
                if full in seen:
                    continue
                try:
                    mt = os.path.getmtime(full)
                except OSError:
                    continue
                if mt < cutoff:
                    continue
                seen.add(full)
                out.append(
                    _issue(
                        nombre=f"Binario hack reciente en temp/downloads: {name}",
                        ruta=root,
                        archivo=full,
                        tipo="temp_hack_binary",
                        categoria="HACKS",
                        alerta="CRITICAL",
                        confidence=0.88,
                        timestamp=iso_from_epoch(mt),
                        detected_patterns=[f"temp_binary:{stem}"],
                        explicacion=(
                            f"{name} (stem={stem}) en {root} modificado en últimas 48h."
                        ),
                    )
                )
                if len(out) >= 12:
                    return out
        except OSError:
            continue
    return out


def run_high_value_checks(app: Any) -> List[dict]:
    findings: List[dict] = []
    for fn in (
        scan_ghost_registry_extended,
        scan_ghost_configs_from_catalog,
        scan_recycle_hack_names,
        scan_desktop_launchers,
        scan_startup_hack_launchers,
        scan_temp_hack_named_exes,
    ):
        try:
            findings.extend(fn(app) or [])
        except Exception as e:
            print(f"[high_value] {fn.__name__}: {e}")
    # Log catálogo
    cat = load_signature_catalog()
    if cat.get("semver"):
        print(f"[signatures] catalog v{cat.get('semver')} loaded")
        try:
            app.signature_catalog_version = cat.get("semver")
        except Exception:
            pass
    return findings
