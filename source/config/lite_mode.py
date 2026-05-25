"""
Argus Scanner — Lite Mode
Auto-detección de hardware bajo (≤4GB RAM, ≤2 cores, Windows ≤8.1).
Recorta hilos, fases secundarias, animaciones UI y profundidad para que
funcione sin cuelgues en Celeron + 4GB RAM + Win8.
"""
from __future__ import annotations

import os
import platform
import sys
from typing import Tuple

_LITE_CACHE: dict = {}


def _detect_hw() -> Tuple[int, float, str]:
    """(cores, ram_gb, win_version_str)"""
    try:
        import psutil
        cores = psutil.cpu_count(logical=True) or 2
        ram = psutil.virtual_memory().total / (1024 ** 3)
    except Exception:
        cores = 2
        ram = 4.0
    win_ver = platform.version()  # e.g. "6.2.9200" (Win8)
    return cores, ram, win_ver


def _win_major() -> int:
    try:
        return int(platform.version().split('.')[0])
    except Exception:
        return 10


def is_lite_needed() -> bool:
    """True si la PC necesita modo lite automáticamente."""
    if 'lite' in _LITE_CACHE:
        return _LITE_CACHE['lite']
    cores, ram, _ = _detect_hw()
    win = _win_major()
    needed = (cores <= 2 or ram <= 4.5 or win < 10)
    _LITE_CACHE['lite'] = needed
    return needed


def lite_max_workers() -> int:
    cores, ram, _ = _detect_hw()
    if ram <= 3 or cores <= 1:
        return 1
    if cores <= 2 or ram <= 4.5:
        return 2
    return min(4, cores)


def lite_scan_timeout() -> int:
    cores, ram, _ = _detect_hw()
    if ram <= 3:
        return 120
    if cores <= 2:
        return 100
    return 85


def lite_phase_timeout() -> int:
    """Timeout por fase secundaria individual."""
    if is_lite_needed():
        return 5
    return 8


def lite_max_depth() -> int:
    if is_lite_needed():
        return 4
    return 8


# Fases que se OMITEN en Lite (consumen mucha RAM/CPU y dan poco valor)
LITE_SKIP_PHASES = frozenset({
    'scan_process_memory_strings',
    'scan_java_rwx_memory',
    'scan_exe_entropy_and_packing',
    'scan_dll_injection_java',
    'scan_java_dll_nonstandard',
    'scan_process_hashes_cloud',
    'scan_player_baseline_delta',
    'scan_config_tfidf',
    'scan_srum_artifacts',
    'scan_thumbcache_artifacts',
    'scan_peb_unlink_mismatch',
    'scan_wifi_promiscuous_mode',
    'scan_firmware_uefi_indicators',
    'scan_suspicious_kernel_drivers',
    'scan_nbt_exploits_saves',
    'scan_shadow_copy_artifacts',
    'scan_modular_scanners',
    'scan_browser_extensions_suspicious',
    'scan_browser_history_sites',
    'scan_browser_downloads',
    'scan_browser_history_cheats',
    'scan_office_mru_registry',
    'scan_virtual_audio_cable',
    'scan_git_repos_desktop',
    'scan_crash_dumps',
    'scan_amcache_unique_sha1',
    'scan_sysmon_operational',
    'scan_security_4688_events',
    'scan_process_crosscheck',
    'scan_wmi_event_subscriptions',
    'scan_ip_forwarding',
    'scan_packet_sniffers',
    'scan_java_suspicious_tls',
    'scan_prescan_disk_activity',
    'scan_process_tree',
    'scan_process_path_correlation',
    'scan_temp_dlls',
    'scan_multiple_javaw',
    'scan_dll_sideloading',
    'scan_system_signed_tamper',
    'scan_appcompat_shimcache',
    'scan_pca_telemetry',
    'scan_muicache',
    'scan_typed_paths',
    'scan_windows_search_history',
    'scan_recent_msi_installs',
    'scan_jdk_installed',
    'scan_lunar_unofficial_modules',
    'scan_minecraft_safe_mode',
    'scan_f3t_log_exploit',
    'scan_options_resolution_mismatch',
})

# Fases ESENCIALES que SIEMPRE corren
LITE_ESSENTIAL_PHASES = frozenset({
    'scan_processes',
    'scan_minecraft_mods_blacklist',
    'scan_prefetch_jna',
    'scan_registry_suspicious',
    'scan_dns_cache',
    'scan_active_injectors',
    'scan_ghost_client_configs',
    'scan_common_hack_locations',
    'scan_exact_hack_names',
    'scan_ahk_scripts',
    'scan_prefetch_hacks',
    'scan_usn_minecraft_jars',
    'scan_defender_exclusions',
    'scan_startup_entries',
    'scan_installed_programs',
    'scan_hosts_file',
    'scan_usb_history',
    'scan_cheat_engine',
    'scan_hack_fingerprints',
    'scan_clipboard_content',
    'scan_scan_options_txt_keybinds',
})


def should_skip_phase(fn_name: str) -> bool:
    if not is_lite_needed():
        return False
    return fn_name in LITE_SKIP_PHASES


def lite_ui_config() -> dict:
    """Ajustes para ModernUI cuando es modo lite."""
    if not is_lite_needed():
        return {}
    return {
        'ui_reduced_motion': True,
        'ui_compact': True,
        'ambient_tick_ms': 200,   # normal: 40ms
        'shimmer_tick_ms': 300,   # normal: 60ms
        'badge_pulse_ms': 1200,   # normal: 450ms
        'ring_tween': False,
        'confetti': False,
        'sparkline': False,
    }


def print_lite_banner():
    cores, ram, win_ver = _detect_hw()
    win = _win_major()
    print("=" * 60)
    print("⚡ ARGUS SCANNER — MODO LITE ACTIVADO")
    print(f"   CPU: {cores} cores · RAM: {ram:.1f} GB · Windows {win_ver}")
    if win < 10:
        print(f"   ⚠ Windows antiguo (v{win}) — compatibilidad reducida")
    print(f"   Hilos: {lite_max_workers()} · Timeout: {lite_scan_timeout()}s")
    print(f"   Fases omitidas: {len(LITE_SKIP_PHASES)} (pesadas/RAM-intensive)")
    print(f"   UI: sin animaciones, compacta")
    print("=" * 60)
