"""Rutas a recursos empaquetados (PyInstaller _MEIPASS)."""
from __future__ import annotations

import os
import shutil
import struct
import sys


def meipass_path(*parts: str) -> str:
    if getattr(sys, 'frozen', False):
        base = getattr(sys, '_MEIPASS', '')
    else:
        base = os.path.dirname(os.path.abspath(__file__))
    return os.path.join(base, *parts)


def bundle_path(*parts: str) -> str:
    return meipass_path('bundle', *parts)


def ensure_scanner_db() -> str:
    """Copia scanner_db embebido junto al .exe si no existe o es más chico."""
    bundled = bundle_path('scanner_db.sqlite')
    if not os.path.isfile(bundled):
        return 'scanner_db.sqlite'
    if getattr(sys, 'frozen', False):
        target = os.path.join(os.path.dirname(sys.executable), 'scanner_db.sqlite')
    else:
        target = os.path.join(os.path.dirname(__file__), 'scanner_db.sqlite')
    try:
        if (not os.path.isfile(target)
                or os.path.getsize(bundled) > os.path.getsize(target)):
            shutil.copy2(bundled, target)
    except OSError:
        pass
    return target


def _override_dirs() -> list[str]:
    """Rutas hot-reload sin recompilar el .exe (v1.8)."""
    dirs: list[str] = []
    local = os.environ.get('LOCALAPPDATA') or os.environ.get('APPDATA') or ''
    if local:
        dirs.append(os.path.join(local, 'ArgusScanner', 'signatures'))
    if getattr(sys, 'frozen', False):
        dirs.append(os.path.join(os.path.dirname(sys.executable), 'signatures'))
    else:
        dirs.append(os.path.join(os.path.dirname(os.path.abspath(__file__)), 'signatures'))
    return dirs


def resolve_signature_file(filename: str) -> str | None:
    """Prioriza override local → bundle/signatures → bundle raíz."""
    for d in _override_dirs():
        p = os.path.join(d, filename)
        if os.path.isfile(p):
            return p
    for cand in (
        bundle_path('signatures', filename),
        bundle_path(filename),
    ):
        if os.path.isfile(cand):
            return cand
    return None


def load_signature_catalog() -> dict:
    """Catálogo versionado (semver) de firmas offline."""
    path = resolve_signature_file('catalog.json')
    if not path:
        return {}
    try:
        import json
        with open(path, 'r', encoding='utf-8') as f:
            data = json.load(f) or {}
        if data.get('semver'):
            print(f'[bundle] signatures catalog v{data.get("semver")}')
        return data
    except Exception:
        return {}


def load_offline_lexicon() -> dict:
    path = resolve_signature_file('offline_lexicon.json')
    if not path:
        return {}
    try:
        import json
        with open(path, 'r', encoding='utf-8') as f:
            data = json.load(f) or {}
        if path and 'signatures' in path.replace('\\', '/'):
            print(f'[bundle] lexicon hot-reload: {path}')
        return data
    except Exception:
        return {}


def load_hash_catalog_hex() -> set[str]:
    """Lee offline_hash_catalog.bin (AHC2) → set de sha256 hex."""
    path = resolve_signature_file('offline_hash_catalog.bin')
    if not path:
        return set()
    out: set[str] = set()
    try:
        with open(path, 'rb') as f:
            magic = f.read(4)
            if magic != b'AHC2':
                return out
            _ver, count = struct.unpack('<II', f.read(8))
            for _ in range(count):
                digest = f.read(32)
                if len(digest) == 32:
                    out.add(digest.hex())
        if path and 'signatures' in path.replace('\\', '/'):
            print(f'[bundle] hash catalog hot-reload: {path} ({len(out)})')
    except Exception:
        pass
    return out


def load_cloud_hashes_json() -> list:
    for name in ('hack_hashes_cloud.json', 'hack_hashes_offline.json'):
        path = resolve_signature_file(name) or bundle_path(name)
        if not path or not os.path.isfile(path):
            continue
        try:
            import json
            with open(path, 'r', encoding='utf-8') as f:
                data = json.load(f)
            if isinstance(data, dict):
                return data.get('hashes') or []
            if isinstance(data, list):
                return data
        except Exception:
            continue
    return []


def offline_ai_model_path() -> str | None:
    p = bundle_path('ai_model_offline.json')
    return p if os.path.isfile(p) else None


def ui_asset_path(filename: str) -> str | None:
    p = bundle_path('ui_assets', filename)
    return p if os.path.isfile(p) else None


def staff_guide_path() -> str | None:
    p = bundle_path('docs', 'staff_guide_offline.html')
    return p if os.path.isfile(p) else None
