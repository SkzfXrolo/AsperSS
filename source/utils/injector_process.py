"""Detección de procesos inyector activos — matching con límites anti-FP."""
from __future__ import annotations

from typing import Optional

# Firmas de procesos inyector / memory editors (nombre normalizado sin espacios/_/-)
INJECTOR_PROCESS_SIGS: tuple[str, ...] = (
    'extremeinjector', 'xenos', 'dllinjector', 'dll_injector',
    'processhacker', 'cheatengine', 'cheat_engine', 'ce32', 'ce64',
    'scylla', 'scyllahide', 'titan', 'injex', 'remoteinjector',
    'manualmap', 'threadhijack',
)

# Procesos Windows legítimos que contienen substrings de firmas cortas (p. ej. ce32 en service32)
INJECTOR_PROCESS_WHITELIST_EXACT: frozenset[str] = frozenset({
    'wallpaperservice32.exe',
    'desktopwallpaperengine.exe',
})

INJECTOR_PROCESS_WHITELIST_PREFIXES: tuple[str, ...] = (
    'wallpaperservice32',
)


def normalize_process_token(value: str) -> str:
    return (value or '').lower().replace(' ', '').replace('-', '').replace('_', '')


def is_injector_process_whitelisted(raw_name: str, exe_path: str = '') -> bool:
    raw = (raw_name or '').lower()
    if raw in INJECTOR_PROCESS_WHITELIST_EXACT:
        return True
    norm = normalize_process_token(raw)
    for prefix in INJECTOR_PROCESS_WHITELIST_PREFIXES:
        if norm.startswith(prefix):
            return True
    norm_exe = normalize_process_token(exe_path)
    if norm_exe and any(prefix in norm_exe for prefix in INJECTOR_PROCESS_WHITELIST_PREFIXES):
        return True
    return False


def _base_name_without_exe(normalized: str) -> str:
    base = normalized
    if base.endswith('.exe'):
        return base[:-4]
    return base


def _short_sig_matches(sig: str, normalized: str) -> bool:
    """Firmas ≤4 chars solo como segmento (evita ce32 dentro de wallpaperservice32)."""
    base = _base_name_without_exe(normalized)
    if not base or not sig:
        return False
    if base == sig:
        return True
    if base.startswith(sig):
        rest = base[len(sig):]
        if rest == '' or rest[0] in '._':
            return True
    if base.endswith(sig):
        prefix = base[:-len(sig)]
        if prefix == '' or prefix[-1] in '._':
            return True
    return False


def match_injector_process(raw_name: str, exe_path: str = '') -> Optional[str]:
    """
    Devuelve la firma que matcheó o None si el proceso no es inyector sospechoso.
    """
    if is_injector_process_whitelisted(raw_name, exe_path):
        return None
    norm_name = normalize_process_token(raw_name)
    norm_exe = normalize_process_token(exe_path)
    for sig in INJECTOR_PROCESS_SIGS:
        # Firmas cortas solo como segmento (ce32, xenos, titan, injex…)
        if len(sig) <= 5:
            if _short_sig_matches(sig, norm_name) or _short_sig_matches(sig, norm_exe):
                return sig
        elif sig in norm_name or sig in norm_exe:
            return sig
    return None
