"""
Argus Scanner Lite — Configuración de modo ligero.

Cuando ARGUS_LITE=1 en env, el scanner recorta hilos, fases pesadas,
animaciones UI y profundidad. Pensado para PCs <=4GB RAM, Celeron, Win8.
"""
from __future__ import annotations

import os


def is_lite() -> bool:
    return os.environ.get('ARGUS_LITE', '') == '1'


def lite_max_workers() -> int:
    if is_lite():
        return 2
    return 8


def lite_scan_timeout() -> int:
    if is_lite():
        return 120
    return 85


def lite_phase_timeout() -> int:
    if is_lite():
        return 5
    return 8


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


def should_skip_phase(fn_name: str) -> bool:
    if not is_lite():
        return False
    return fn_name in LITE_SKIP_PHASES
