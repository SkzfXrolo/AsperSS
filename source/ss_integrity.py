"""
SS Integrity Pack — detecciones de anti-forensics / bypass que Ocean y Echo
priorizan como señal primaria (no como ruido).

Objetivo: flaggear *limpieza de evidencia*, no solo presencia de cheats.
Ejecuta sin drivers kernel. Seguro para hot-path de SS.
"""
from __future__ import annotations

import os
import subprocess
import time
from typing import Any


_CLEANER_NAMES = (
    "ccleaner", "bleachbit", "privazer", "revo", "wise care", "glary",
    "prefetch cleaner", "amcache cleaner", "usbdeview", "sdelete",
    "cipher.exe", "eraser", "bcwipe", "dban",
)


def scan_integrity(app=None) -> list[dict[str, Any]]:
    findings: list[dict[str, Any]] = []
    now = time.time()

    findings.extend(_check_prefetch_integrity(now))
    findings.extend(_check_recycle_wipe(now))
    findings.extend(_check_eventlog_wipe())
    findings.extend(_check_cleaner_artifacts(now))
    findings.extend(_check_powershell_bypass(now))
    findings.extend(_check_usn_delete_journal(app))
    findings.extend(_check_recent_docs_wipe(now))
    findings.extend(_check_prefetch_bam_gap(now))

    for f in findings:
        f.setdefault("categoria", "INTEGRITY")
        f.setdefault("tipo", "ss_integrity")
        f.setdefault("confidence", 0.75)
    return findings


def _finding(nombre, alerta, explicacion, patterns, confidence=0.78, **extra):
    out = {
        "nombre": nombre,
        "ruta": extra.pop("ruta", ""),
        "archivo": extra.pop("archivo", ""),
        "tipo": "ss_integrity",
        "categoria": "INTEGRITY",
        "alerta": alerta,
        "confidence": confidence,
        "detected_patterns": patterns,
        "explicacion": explicacion,
    }
    out.update(extra)
    return out


def _check_prefetch_integrity(now: float) -> list[dict]:
    """Ocean: Prefetch deleted / mass wipe = bypass."""
    pf_dir = r"C:\Windows\Prefetch"
    out = []
    if not os.path.isdir(pf_dir):
        out.append(_finding(
            "Carpeta Prefetch inaccesible o ausente",
            "SOSPECHOSO",
            "Sin Prefetch no hay rastro de ejecución. En Windows 10/11 normal "
            "esto suele indicar privilegios restringidos o limpieza antiforense.",
            ["integrity:prefetch_missing"],
            confidence=0.65,
            ruta=pf_dir,
        ))
        return out

    try:
        entries = [e for e in os.listdir(pf_dir) if e.lower().endswith(".pf")]
    except OSError:
        return out

    n = len(entries)
    # Máquina con uso normal suele tener cientos de .pf; <40 es anómalo en SS
    if n < 25:
        out.append(_finding(
            f"Prefetch casi vacío ({n} archivos .pf)",
            "CRITICAL" if n < 10 else "SOSPECHOSO",
            f"Solo hay {n} Prefetch. Un Windows usado normalmente acumula "
            "cientos. Borrado masivo de .pf es técnica clásica de bypass SS "
            "(Ocean/Echo lo tratan como integridad rota).",
            [f"integrity:prefetch_count:{n}"],
            confidence=0.88 if n < 10 else 0.80,
            ruta=pf_dir,
        ))

    # Borrados recientes: muchos .pf tocados en las últimas 2h
    recent_touch = 0
    for name in entries[:400]:
        try:
            st = os.stat(os.path.join(pf_dir, name))
            if now - st.st_mtime < 7200:
                recent_touch += 1
        except OSError:
            continue
    if n >= 40 and recent_touch >= max(30, int(n * 0.35)):
        out.append(_finding(
            f"Prefetch masivamente regenerado/tocado ({recent_touch}/{n} en 2h)",
            "SOSPECHOSO",
            "Muchos Prefetch modificados en las últimas 2 horas. Suele indicar "
            "borrado + regeneración tras ejecutar un cleaner o un bypass.",
            [f"integrity:prefetch_recent_touch:{recent_touch}"],
            confidence=0.72,
            ruta=pf_dir,
        ))
    return out


def _check_recycle_wipe(now: float) -> list[dict]:
    """Echo: recycle bin cleared cerca del SS."""
    out = []
    drives = []
    for letter in "CDEFG":
        root = f"{letter}:\\$Recycle.Bin"
        if os.path.isdir(root):
            drives.append(root)

    wiped_signals = 0
    for root in drives:
        try:
            # Si el directorio existe pero no hay $I* recientes y mtime del bin es fresco
            st = os.stat(root)
            if now - st.st_mtime < 86400:
                # Contar $I files
                count_i = 0
                for dirpath, _, files in os.walk(root):
                    for f in files:
                        if f.startswith("$I") or f.startswith("$R"):
                            count_i += 1
                    if count_i > 20:
                        break
                if count_i == 0 and (now - st.st_mtime) < 43200:
                    wiped_signals += 1
        except OSError:
            continue

    if wiped_signals:
        out.append(_finding(
            "Papelera vaciada recientemente (posible wipe pre-SS)",
            "SOSPECHOSO",
            "La Papelera muestra señales de vaciado reciente sin residuos $I/$R. "
            "Echo marca esto como indicador de limpieza previa al screenshare.",
            [f"integrity:recycle_wipe:{wiped_signals}"],
            confidence=0.70,
        ))
    return out


def _check_eventlog_wipe() -> list[dict]:
    out = []
    try:
        sec = subprocess.run(
            ["wevtutil", "qe", "Security", "/q:*[System[(EventID=1102)]]",
             "/c:5", "/rd:true", "/f:text"],
            capture_output=True, timeout=8, creationflags=0x08000000,
        )
        if (sec.stdout or b"").strip():
            out.append(_finding(
                "Security log cleared (Event 1102)",
                "CRITICAL",
                "Se borró el log de Seguridad. En SS esto es bypass antiforense "
                "casi siempre deliberado (Ocean: integrity check).",
                ["integrity:eventlog_1102"],
                confidence=0.92,
            ))
    except Exception:
        pass
    try:
        sys = subprocess.run(
            ["wevtutil", "qe", "System", "/q:*[System[(EventID=104)]]",
             "/c:5", "/rd:true", "/f:text"],
            capture_output=True, timeout=8, creationflags=0x08000000,
        )
        if (sys.stdout or b"").strip():
            out.append(_finding(
                "System log cleared (Event 104)",
                "SOSPECHOSO",
                "Se borró el log de Sistema. Combinado con otras señales de "
                "integridad eleva fuertemente la sospecha de bypass.",
                ["integrity:eventlog_104"],
                confidence=0.80,
            ))
    except Exception:
        pass
    return out


def _check_cleaner_artifacts(now: float) -> list[dict]:
    """Prefetch / Recent de cleaners conocidos cerca del SS."""
    out = []
    pf_dir = r"C:\Windows\Prefetch"
    if not os.path.isdir(pf_dir):
        return out
    try:
        names = os.listdir(pf_dir)
    except OSError:
        return out

    hits = []
    for name in names:
        low = name.lower()
        if not low.endswith(".pf"):
            continue
        if any(c in low for c in _CLEANER_NAMES):
            path = os.path.join(pf_dir, name)
            try:
                age_h = (now - os.stat(path).st_mtime) / 3600.0
            except OSError:
                age_h = 999.0
            if age_h <= 72:
                hits.append((name, age_h))

    if hits:
        hits.sort(key=lambda x: x[1])
        top = hits[0]
        alerta = "CRITICAL" if top[1] <= 6 else "SOSPECHOSO"
        out.append(_finding(
            f"Cleaner antiforense ejecutado: {top[0]} (hace {top[1]:.1f}h)",
            alerta,
            "Se ejecutó una herramienta de limpieza (CCleaner/BleachBit/etc.) "
            "cerca del SS. En pantallas de Echo/Ocean esto es integridad rota "
            "y suele ir ligado a wipe de Prefetch/BAM/USN.",
            [f"integrity:cleaner:{top[0][:40]}"],
            confidence=0.90 if top[1] <= 6 else 0.78,
            ruta=os.path.join(pf_dir, top[0]),
            archivo=top[0],
        ))
    return out


def _check_powershell_bypass(now: float) -> list[dict]:
    """PowerShell con comandos de wipe (Echo lo destaca)."""
    out = []
    # ConsoleHost_history.txt
    hist = os.path.expandvars(
        r"%APPDATA%\Microsoft\Windows\PowerShell\PSReadLine\ConsoleHost_history.txt"
    )
    if not os.path.isfile(hist):
        return out
    try:
        age_h = (now - os.stat(hist).st_mtime) / 3600.0
        if age_h > 96:
            return out
        with open(hist, "r", encoding="utf-8", errors="ignore") as f:
            # Solo cola reciente
            lines = f.readlines()[-200:]
        blob = "\n".join(lines).lower()
    except OSError:
        return out

    triggers = []
    if "wevtutil cl" in blob or "clear-eventlog" in blob:
        triggers.append("clear_eventlog")
    if "fsutil usn deletejournal" in blob:
        triggers.append("usn_deletejournal")
    if "prefetch" in blob and ("remove-item" in blob or "del " in blob or "rm " in blob):
        triggers.append("prefetch_wipe_ps")
    if "bam" in blob and "reg delete" in blob:
        triggers.append("bam_reg_delete")

    if triggers:
        out.append(_finding(
            f"PowerShell bypass/wipe detectado: {', '.join(triggers)}",
            "CRITICAL",
            "Historial reciente de PowerShell contiene comandos de borrado de "
            "logs / Prefetch / USN / BAM. Es bypass deliberado de SS.",
            [f"integrity:ps:{t}" for t in triggers],
            confidence=0.93,
            ruta=hist,
        ))
    return out


def _check_usn_delete_journal(app) -> list[dict]:
    """Si el scan ya cacheó USN vacío tras haber tenido admin, señal débil."""
    out = []
    cache = getattr(app, "_usn_cache", None) if app is not None else None
    if cache is None:
        return out
    # Si alguien corrió deletejournal, fsutil suele fallar o devolver vacío
    if isinstance(cache, (list, tuple)) and len(cache) == 0:
        # Solo flag si el proceso cree que tenía admin
        if getattr(app, "_had_admin_for_usn", False):
            out.append(_finding(
                "USN Journal vacío con privilegios admin",
                "SOSPECHOSO",
                "Con admin el USN debería devolver actividad. Vacío sugiere "
                "deletejournal o journal deshabilitado (bypass forense).",
                ["integrity:usn_empty"],
                confidence=0.68,
            ))
    return out


def _check_recent_docs_wipe(now: float) -> list[dict]:
    """RecentDocs / AutomaticDestinations vacíos tras uso reciente = wipe."""
    out = []
    recent = os.path.expandvars(r"%APPDATA%\Microsoft\Windows\Recent")
    auto = os.path.expandvars(
        r"%APPDATA%\Microsoft\Windows\Recent\AutomaticDestinations"
    )
    try:
        if os.path.isdir(recent):
            entries = [e for e in os.listdir(recent) if not e.startswith(".")]
            st = os.stat(recent)
            if len(entries) < 3 and (now - st.st_mtime) < 86400:
                out.append(_finding(
                    f"Carpeta Recent casi vacía ({len(entries)} items, tocada <24h)",
                    "SOSPECHOSO",
                    "Recent Docs vacío con mtime reciente suele indicar cleaner "
                    "o wipe manual previo al SS.",
                    [f"integrity:recent_wipe:{len(entries)}"],
                    confidence=0.72,
                    ruta=recent,
                ))
        if os.path.isdir(auto):
            autos = os.listdir(auto)
            if len(autos) == 0:
                out.append(_finding(
                    "AutomaticDestinations vacío (Jump Lists wipe)",
                    "SOSPECHOSO",
                    "Jump Lists borrados — técnica antiforense común en SS.",
                    ["integrity:jumplist_wipe"],
                    confidence=0.70,
                    ruta=auto,
                ))
    except OSError:
        pass
    return out


def _check_prefetch_bam_gap(now: float) -> list[dict]:
    """
    Prefetch con pocos .pf pero BAM/UserAssist con actividad reciente implica
    que se borraron Prefetch tras ejecutar software (gap clásico Ocean).
    """
    out = []
    pf_dir = r"C:\Windows\Prefetch"
    if not os.path.isdir(pf_dir):
        return out
    try:
        pfs = [e for e in os.listdir(pf_dir) if e.lower().endswith(".pf")]
    except OSError:
        return out
    if len(pfs) >= 40:
        return out

    # Señal BAM: clave existe y tiene valores recientes (lectura shallow)
    bam_hits = 0
    try:
        import winreg
        bam_path = (
            r"SYSTEM\CurrentControlSet\Services\bam\State\UserSettings"
        )
        with winreg.OpenKey(winreg.HKEY_LOCAL_MACHINE, bam_path, 0,
                            winreg.KEY_READ | winreg.KEY_WOW64_64KEY) as k:
            i = 0
            while i < 8:
                try:
                    sub = winreg.EnumKey(k, i)
                except OSError:
                    break
                i += 1
                try:
                    with winreg.OpenKey(k, sub) as sk:
                        # Contar valores como proxy de actividad
                        j = 0
                        while j < 20:
                            try:
                                winreg.EnumValue(sk, j)
                                j += 1
                                bam_hits += 1
                            except OSError:
                                break
                except OSError:
                    continue
    except Exception:
        return out

    if bam_hits >= 8 and len(pfs) < 25:
        out.append(_finding(
            f"Gap Prefetch/BAM: {len(pfs)} .pf vs BAM activo ({bam_hits}+)",
            "CRITICAL",
            "Hay actividad de ejecución en BAM pero Prefetch está casi vacío. "
            "Patrón típico de borrado selectivo de Prefetch tras usar cheats "
            "(integridad rota — Ocean/Echo).",
            [f"integrity:prefetch_bam_gap:pf={len(pfs)}:bam={bam_hits}"],
            confidence=0.86,
            ruta=pf_dir,
        ))
    return out
