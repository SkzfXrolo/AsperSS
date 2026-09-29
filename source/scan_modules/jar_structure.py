"""P2 #18/#19/#20 — Manifest, estructura y timestamp compile vs mtime."""
from __future__ import annotations

import os
import time
import zipfile
from datetime import datetime
from typing import Any, List, Optional, Tuple


_LEGIT_MAIN = (
    "net.fabricmc",
    "net.minecraftforge",
    "net.neoforged",
    "org.quiltmc",
    "cpw.mods",
    "net.minecraft",
    "com.mojang",
    "org.spongepowered",
)

_MOD_MARKERS = (
    "fabric.mod.json",
    "quilt.mod.json",
    "mods.toml",
    "neoforge.mods.toml",
    "mcmod.info",
    "riftmod.json",
    "litemod.json",
)


def _zip_entry_mtime(zinfo: zipfile.ZipInfo) -> Optional[float]:
    try:
        return time.mktime(zinfo.date_time + (0, 0, -1))
    except Exception:
        return None


def _repack_anomaly(zf: zipfile.ZipFile, fpath: str) -> Optional[Tuple[str, float]]:
    """P2 #20 — class ZIP dates recientes vs mtime del jar antiguo."""
    try:
        jar_mtime = os.path.getmtime(fpath)
    except OSError:
        return None
    age_jar_days = (time.time() - jar_mtime) / 86400
    if age_jar_days < 7:
        return None  # jar reciente: no aplica el truco de backdate
    newest_class = 0.0
    for zi in zf.infolist():
        if not zi.filename.lower().endswith(".class"):
            continue
        mt = _zip_entry_mtime(zi)
        if mt and mt > newest_class:
            newest_class = mt
    if newest_class <= 0:
        return None
    # Class "compilado" en últimas 24h pero jar mtime viejo → re-empaquetado
    if (time.time() - newest_class) < 86400 and age_jar_days > 14:
        return (
            f"class_zip_ts={datetime.fromtimestamp(newest_class).isoformat(timespec='seconds')} "
            f"jar_mtime={datetime.fromtimestamp(jar_mtime).isoformat(timespec='seconds')}",
            newest_class,
        )
    return None


def scan_mods_jar_structure(app: Any) -> List[dict]:
    """JARs en .minecraft/mods sin metadata de mod / re-empaquetados."""
    appdata = os.environ.get("APPDATA", "")
    mods = os.path.join(appdata, ".minecraft", "mods")
    if not os.path.isdir(mods):
        return []
    out: List[dict] = []
    try:
        names = os.listdir(mods)
    except OSError:
        return []
    for fname in names:
        if not fname.lower().endswith(".jar"):
            continue
        fpath = os.path.join(mods, fname)
        try:
            size = os.path.getsize(fpath)
        except OSError:
            continue
        if size < 3072 or size > 80 * 1024 * 1024:
            continue
        try:
            with zipfile.ZipFile(fpath, "r") as zf:
                names_l = [n.lower() for n in zf.namelist()]
                has_mod_meta = any(any(m in n for n in names_l) for m in _MOD_MARKERS)
                main_class = ""
                try:
                    mf = zf.read("META-INF/MANIFEST.MF").decode("utf-8", errors="ignore")
                    for line in mf.splitlines():
                        if line.lower().startswith("main-class:"):
                            main_class = line.split(":", 1)[1].strip()
                            break
                except KeyError:
                    pass
                legit_main = (
                    any(main_class.lower().startswith(p) for p in _LEGIT_MAIN)
                    if main_class
                    else False
                )
                repack = _repack_anomaly(zf, fpath)
                if repack:
                    detail, _ = repack
                    out.append({
                        "nombre": f"JAR re-empaquetado reciente (mtime viejo): {fname}",
                        "ruta": fpath,
                        "archivo": fname,
                        "tipo": "jar_repack_timestamp",
                        "categoria": "HACKS",
                        "alerta": "SOSPECHOSO",
                        "confidence": 0.74,
                        "detected_patterns": ["jar_repack_timestamp_mismatch"],
                        "explicacion": (
                            f"{fname}: entradas .class con fecha ZIP reciente pero "
                            f"mtime del archivo antiguo. {detail}"
                        ),
                        "extra": {"detail": detail, "file_size": size},
                    })

                if has_mod_meta:
                    continue
                if main_class and legit_main:
                    continue
                # FP: nombre tipico de mod performance aunque falte meta (corrupt/parcial)
                fl = fname.lower()
                if any(
                    fl.startswith(p) or f"-{p}" in fl or f"_{p}" in fl
                    for p in (
                        "sodium", "lithium", "iris", "ferritecore", "lazydfu",
                        "entityculling", "fabric-api", "modmenu", "cloth-config",
                        "indium", "starlight", "dynamic-fps", "moreculling",
                    )
                ):
                    continue
                alerta = "CRITICAL" if main_class and not legit_main else "SOSPECHOSO"
                conf = 0.78 if main_class else 0.62
                out.append({
                    "nombre": f"JAR en mods/ sin metadata de mod: {fname}",
                    "ruta": fpath,
                    "archivo": fname,
                    "tipo": "jar_missing_mod_metadata",
                    "categoria": "HACKS",
                    "alerta": alerta,
                    "confidence": conf,
                    "detected_patterns": (
                        ["no_mod_metadata"]
                        + ([f"main_class:{main_class[:80]}"] if main_class else ["no_main_class"])
                    ),
                    "explicacion": (
                        f"{fname} está en mods/ pero no tiene fabric.mod.json / mods.toml / mcmod.info. "
                        + (
                            f"Main-Class={main_class}."
                            if main_class
                            else "Tampoco declara Main-Class típica de loader."
                        )
                    ),
                    "extra": {"main_class": main_class, "file_size": size},
                })
                if len(out) >= 15:
                    break
        except (zipfile.BadZipFile, OSError):
            continue
    return out
