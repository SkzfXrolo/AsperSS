"""
Pack v1.7 — superficies forenses NUEVAS (no duplicar grep en Descargas).

Incluye:
  • Cada módulo en source/scanners/ (28) — hoy main solo corre 7 vía aggregator
  • Cada técnica SSForensics por separado (28) — toggle individual
  • Artefactos de launchers, capture, remote, periféricos, etc. (25+)
"""
from __future__ import annotations

import glob
import importlib
import os
import re
import sqlite3
import shutil
import tempfile
import time
from pathlib import Path

from scan_modules.scanner_bridge import convert_scanner_output, _issue

# ── Scanner package (28 módulos) ───────────────────────────────────────────

_SCANNER_SPECS = [
    ('pkg_registry_anomalies', 'Registro Run/IFEO anómalo', 'scanners.registry_anomalies', 'scan_registry_anomalies'),
    ('pkg_dns_artifacts', 'Artefactos DNS / hosts', 'scanners.dns_artifacts', 'scan_dns_artifacts'),
    ('pkg_credential_stores', 'Windows Vault / credenciales', 'scanners.credential_stores', 'scan_credential_stores'),
    ('pkg_wmi_subscriptions', 'Suscripciones WMI', 'scanners.wmi_subscriptions', 'scan_wmi_subscriptions'),
    ('pkg_com_objects', 'COM hijacking', 'scanners.com_objects', 'scan_com_objects'),
    ('pkg_scheduled_task_xml', 'Tareas programadas (XML)', 'scanners.scheduled_task_xml', 'scan_scheduled_task_xml'),
    ('pkg_firewall_rules', 'Reglas firewall salientes', 'scanners.firewall_rules', 'scan_firewall_rules'),
    ('pkg_anti_forensics', 'Anti-forensics (logs borrados)', 'scanners.anti_forensics', 'scan_anti_forensics'),
    ('pkg_asep_advanced', 'ASEP avanzado', 'scanners.asep_advanced', 'scan_asep_advanced'),
    ('pkg_browser_history', 'Historial Chrome/Edge/Firefox', 'scanners.browser_history', 'scan_browser_history'),
    ('pkg_clipboard_history', 'Portapapeles Windows 10+', 'scanners.clipboard_history', 'scan_clipboard_history'),
    ('pkg_cryptojacking', 'Procesos minería / CPU', 'scanners.cryptojacking', 'scan_cryptojacking'),
    ('pkg_network_state', 'ARP/rutas/netstat', 'scanners.network_artifacts', 'scan_network_state'),
    ('pkg_startup_locations', 'Run keys + carpetas Startup', 'scanners.startup_locations', 'scan_startup_locations'),
    ('pkg_services_anomalies', 'Servicios Windows raros', 'scanners.services_anomalies', 'scan_services_anomalies'),
    ('pkg_persistence', 'Persistencia consolidada', 'scanners.persistence_consolidated', 'scan_persistence_consolidated'),
    ('pkg_handle_analysis', 'Handles de procesos', 'scanners.handle_analysis', 'scan_process_handles'),
    ('pkg_named_pipes', 'Named pipes', 'scanners.named_pipes', 'scan_named_pipes'),
    ('pkg_etw_consumers', 'Consumidores ETW', 'scanners.etw_consumers', 'scan_etw_consumers'),
    ('pkg_dll_search_order', 'DLL search order hijack', 'scanners.dll_search_order', 'scan_dll_search_order'),
    ('pkg_print_drivers', 'Drivers de impresión', 'scanners.print_drivers', 'scan_print_drivers'),
    ('pkg_uac_bypass', 'Bypass UAC', 'scanners.uac_bypass', 'scan_uac_bypass'),
    ('pkg_keylogger', 'Indicadores keylogger', 'scanners.keylogger_indicators', 'scan_keylogger_indicators'),
    ('pkg_screen_capture', 'Capture / stream tools', 'scanners.screen_capture', 'scan_screen_capture_indicators'),
    ('pkg_lateral_movement', 'Movimiento lateral', 'scanners.lateral_movement_indicators', 'scan_lateral_movement_indicators'),
    ('pkg_cobalt_strike', 'Indicadores Cobalt Strike', 'scanners.cobalt_strike', 'scan_cobalt_strike_indicators'),
    ('pkg_empire', 'Indicadores Empire', 'scanners.empire_indicators', 'scan_empire_indicators'),
    ('pkg_metasploit', 'Indicadores Metasploit', 'scanners.metasploit_indicators', 'scan_metasploit_indicators'),
    ('pkg_ransomware', 'Indicadores ransomware', 'scanners.ransomware_indicators', 'scan_ransomware_indicators'),
]

_FORENSIC_SPECS = [
    ('forensic_usn_journal', 'USN Journal (borrados/creados)', '_scan_usn_journal'),
    ('forensic_appcompat', 'AppCompatFlags (ejecutados)', '_scan_appcompat_store'),
    ('forensic_userassist', 'UserAssist rot13', '_scan_userassist'),
    ('forensic_winrar', 'WinRAR ArcHistory', '_scan_winrar_history'),
    ('forensic_dps', 'Servicio DPS detenido', '_scan_dps_service'),
    ('forensic_usbstor', 'USBSTOR historial USB', '_scan_usbstor'),
    ('forensic_comdlg32', 'ComDlg32 OpenSave MRU', '_scan_comdlg32_mru'),
    ('forensic_cmd_autorun', 'CMD AutoRun processor', '_scan_command_processor'),
    ('forensic_disallow_run', 'DisallowRun / RestrictRun', '_scan_disallow_run'),
    ('forensic_featureusage', 'FeatureUsage alt-tab', '_scan_featureusage'),
    ('forensic_xinputhid', 'Servicio xinputhid', '_scan_xinputhid'),
    ('forensic_mounted_devices', 'MountedDevices volúmenes', '_scan_mounted_devices'),
    ('forensic_prefetch_deep', 'Prefetch análisis profundo', '_scan_prefetch_analysis'),
    ('forensic_tcpip', 'Tcpip interfaces DNS', '_scan_tcpip_interfaces'),
    ('forensic_logitech', 'Macros Logitech LGS/G HUB', '_scan_logitech_macros'),
    ('forensic_razer', 'Macros Razer Synapse', '_scan_razer_macros'),
    ('forensic_dns_cache', 'DNS cache forense', '_scan_dns_cache'),
    ('forensic_autohotkey', 'Scripts AHK recientes', '_scan_autohotkey'),
    ('forensic_time_change', 'Event log cambio hora', '_scan_event_log_time_change'),
    ('forensic_jna', 'Artefactos JNA', '_scan_jna_artifacts'),
    ('forensic_java_mem', 'Java process memory', '_scan_java_process_memory'),
    ('forensic_rar', 'Archivos RAR recientes', '_scan_rar_files'),
    ('forensic_forfiles', 'FORFILES exes recientes', '_scan_recent_exe_forfiles'),
    ('forensic_mmagent', 'MMAgent superfetch', '_scan_mmagent'),
    ('forensic_tray', 'Iconos bandeja ocultos', '_scan_tray_icons'),
    ('forensic_recentdocs', 'RecentDocs registro', '_scan_recentdocs'),
    ('forensic_runmru', 'RunMRU comandos Win+R', '_scan_runmru'),
    ('forensic_amcache', 'Amcache forense', '_scan_amcache'),
    ('forensic_vm', 'Detección VM', '_scan_vm_detection'),
    ('forensic_explorer', 'Explorer strings MRU', '_scan_explorer_strings'),
]


def _get_forensics(ctx):
    if 'ss_forensics' not in ctx.cache:
        try:
            from ss_forensics import SSForensics
            ctx.cache['ss_forensics'] = SSForensics()
        except Exception:
            ctx.cache['ss_forensics'] = None
    return ctx.cache['ss_forensics']


def _make_pkg_module(mod_id, label, module_path, fn_name):
    def _run(ctx):
        try:
            mod = importlib.import_module(module_path)
            fn = getattr(mod, fn_name)
            from scanners._safe_runner import run_safe
            raw = run_safe(fn, timeout=12)
            if not raw.get('ok'):
                return []
            return convert_scanner_output(mod_id, raw.get('result'))
        except Exception as e:
            print(f'[novel {mod_id}] {e}')
            return []
    _run.__doc__ = label
    return _run


def _make_forensic_module(mod_id, label, method_name):
    def _run(ctx):
        sf = _get_forensics(ctx)
        if not sf:
            return []
        try:
            fn = getattr(sf, method_name)
            return fn() or []
        except Exception as e:
            print(f'[novel {mod_id}] {e}')
            return []
    _run.__doc__ = label
    return _run


# ── Superficies custom (launchers, remote, periféricos, bedrock…) ───────────

def _read_text_file(path, limit=12000):
    try:
        return Path(path).read_text(encoding='utf-8', errors='ignore')[:limit]
    except Exception:
        return ''


def _grep_paths(root, needles, max_depth=5, max_hits=6):
    if not root or not os.path.isdir(root):
        return []
    hits = []
    needles = tuple(n.lower() for n in needles)
    for dirpath, dirnames, filenames in os.walk(root):
        if dirpath[len(root):].count(os.sep) >= max_depth:
            dirnames[:] = []
            continue
        for name in dirnames + filenames:
            nl = name.lower()
            if any(n in nl for n in needles):
                hits.append(os.path.join(dirpath, name))
        if len(hits) >= max_hits:
            break
    return hits


def nov_windows_timeline(ctx):
    """Windows Timeline / ActivitiesCache."""
    base = os.path.join(ctx.appdata, 'ConnectedDevicesPlatform')
    if not os.path.isdir(base):
        return []
    out = []
    for db in glob.glob(os.path.join(base, '*', 'ActivitiesCache.db')):
        try:
            tmp = tempfile.NamedTemporaryFile(delete=False, suffix='.db')
            tmp.close()
            shutil.copy2(db, tmp.name)
            conn = sqlite3.connect(tmp.name)
            cur = conn.cursor()
            cur.execute(
                "SELECT AppId, Payload FROM ActivityOperation ORDER BY OperationExpirationTime DESC LIMIT 80"
            )
            for app_id, payload in cur.fetchall():
                blob = (str(app_id) + str(payload)).lower()
                if any(c in blob for c in ('minecraft', 'vape', 'cheat', 'autoclick', 'baritone')):
                    out.append(_issue(
                        'Actividad Timeline sospechosa',
                        db, 'SOSPECHOSO', 'novel_timeline', 0.7,
                        categoria='TIMELINE',
                        detalle=str(app_id)[:80],
                    ))
            conn.close()
            os.remove(tmp.name)
        except Exception:
            pass
        if len(out) >= 5:
            break
    return out[:6]


def nov_lunar_client(ctx):
    root = os.path.join(ctx.userprofile, '.lunarclient')
    if not os.path.isdir(root):
        root = os.path.join(ctx.appdata, 'lunarclient')
    hits = _grep_paths(root, ('cheat', 'inject', 'ghost', 'vape', 'account', 'log'), 4)
    return [_issue('Lunar Client artefacto', h, 'SOSPECHOSO', 'novel_lunar', 0.65) for h in hits[:5]]


def nov_feather_client(ctx):
    root = os.path.join(ctx.appdata, 'Feather Launcher')
    if not os.path.isdir(root):
        root = os.path.join(ctx.appdata, 'feather')
    hits = _grep_paths(root, ('cheat', 'hack', 'log', 'account'), 4)
    logs = glob.glob(os.path.join(root, '**', '*.log'), recursive=True)[:8]
    out = [_issue('Feather launcher', h, 'SOSPECHOSO', 'novel_feather', 0.62) for h in hits[:4]]
    for lg in logs:
        t = _read_text_file(lg, 6000).lower()
        if any(c in t for c in ('vape', 'cheat', 'inject')):
            out.append(_issue('Feather log menciona cheat', lg, 'CRITICAL', 'novel_feather', 0.85))
    return out[:6]


def nov_prism_launcher(ctx):
    roots = [
        os.path.join(ctx.appdata, 'PrismLauncher'),
        os.path.join(ctx.appdata, 'PolyMC'),
        os.path.join(ctx.appdata, 'multimc'),
    ]
    out = []
    for root in roots:
        if not os.path.isdir(root):
            continue
        for ini in glob.glob(os.path.join(root, '**', 'instance.cfg'), recursive=True)[:20]:
            t = _read_text_file(ini, 4000).lower()
            if 'baritone' in t or 'autoclick' in t:
                out.append(_issue('Instancia Prism/Poly con mod sospechoso', ini, 'SOSPECHOSO', 'novel_prism', 0.72))
    return out[:5]


def nov_sharex_history(ctx):
    hist = os.path.join(ctx.userprofile, 'Documents', 'ShareX', 'History.json')
    if not os.path.isfile(hist):
        hist = os.path.join(ctx.appdata, 'ShareX', 'History.json')
    if not os.path.isfile(hist):
        return []
    t = _read_text_file(hist, 15000).lower()
    out = []
    if any(c in t for c in ('vape', 'cheat', 'hack', 'minecraft')):
        out.append(_issue('ShareX historial menciona cheat/MC', hist, 'SOSPECHOSO', 'novel_sharex', 0.6))
    return out


def nov_medal_tv(ctx):
    root = os.path.join(ctx.appdata, 'Medal')
    if not os.path.isdir(root):
        return []
    hits = _grep_paths(root, ('clip', 'minecraft', 'hack'), 3)
    return [_issue('Medal.tv artefacto', h, 'NORMAL', 'novel_medal', 0.4) for h in hits[:3]]


def nov_anydesk_traces(ctx):
    roots = [
        os.path.join(ctx.appdata, 'AnyDesk'),
        os.path.join(os.environ.get('PROGRAMDATA', ''), 'AnyDesk'),
    ]
    out = []
    for root in roots:
        for fn in ('ad.trace', 'connection_trace.txt', 'user.conf'):
            p = os.path.join(root, fn)
            if os.path.isfile(p):
                out.append(_issue('AnyDesk trace / config', p, 'NORMAL', 'novel_anydesk', 0.35))
        hits = _grep_paths(root, ('session', 'trace'), 2)
        out.extend(_issue('AnyDesk archivo', h, 'NORMAL', 'novel_anydesk', 0.35) for h in hits[:2])
    return out[:5]


def nov_teamviewer(ctx):
    root = os.path.join(ctx.appdata, 'TeamViewer')
    if not os.path.isdir(root):
        return []
    logs = glob.glob(os.path.join(root, '**', '*.log'), recursive=True)[:5]
    return [_issue('TeamViewer log presente', lg, 'NORMAL', 'novel_teamviewer', 0.35) for lg in logs]


def nov_rustdesk(ctx):
    root = os.path.join(ctx.appdata, 'RustDesk')
    if not os.path.isdir(root):
        return []
    if os.path.isfile(os.path.join(root, 'config', 'RustDesk.toml')):
        return [_issue('RustDesk configurado en este PC', root, 'NORMAL', 'novel_rustdesk', 0.4)]
    return []


def nov_minecraft_bedrock(ctx):
    root = os.path.join(ctx.appdata, 'Packages')
    if not os.path.isdir(root):
        return []
    out = []
    for name in os.listdir(root):
        if 'minecraft' in name.lower():
            out.append(_issue('Minecraft Bedrock (Microsoft Store)', os.path.join(root, name),
                              'NORMAL', 'novel_bedrock', 0.4))
    return out[:3]


def nov_xbox_game_bar(ctx):
    root = os.path.join(ctx.appdata, 'Local', 'Packages')
    if not os.path.isdir(root):
        return []
    out = []
    for name in os.listdir(root):
        if 'xboxgamingoverlay' in name.lower() or 'gamebar' in name.lower():
            cap = os.path.join(root, name, 'LocalState')
            if os.path.isdir(cap):
                out.append(_issue('Xbox Game Bar / capturas', cap, 'NORMAL', 'novel_xbox', 0.35))
    return out[:3]


def nov_geforce_experience(ctx):
    root = os.path.join(ctx.appdata, 'NVIDIA Corporation')
    logs = glob.glob(os.path.join(root, '**', '*.log'), recursive=True)[:10] if os.path.isdir(root) else []
    return [_issue('Log NVIDIA GeForce', lg, 'NORMAL', 'novel_nvidia', 0.35) for lg in logs[:3]]


def nov_logitech_ghub(ctx):
    root = os.path.join(ctx.appdata, 'LGHUB')
    if not os.path.isdir(root):
        root = os.path.join(ctx.appdata, 'Logitech', 'Logitech Gaming Software')
    settings = glob.glob(os.path.join(root, '**', '*.json'), recursive=True)[:15] if os.path.isdir(root) else []
    out = []
    for js in settings:
        t = _read_text_file(js, 8000).lower()
        if 'macro' in t and ('click' in t or 'repeat' in t or 'minecraft' in t):
            out.append(_issue('Logitech G HUB macro detectada', js, 'SOSPECHOSO', 'novel_ghub', 0.68))
    return out[:4]


def nov_steelseries_gg(ctx):
    root = os.path.join(ctx.appdata, 'steelseries-gg')
    if not os.path.isdir(root):
        return []
    hits = _grep_paths(root, ('macro', 'binding'), 4)
    return [_issue('SteelSeries GG binding', h, 'SOSPECHOSO', 'novel_steelseries', 0.55) for h in hits[:4]]


def nov_corsair_icue(ctx):
    root = os.path.join(ctx.appdata, 'Corsair')
    if not os.path.isdir(root):
        return []
    hits = _grep_paths(root, ('macro', 'profile', 'cueprofile'), 5)
    return [_issue('Corsair iCUE perfil/macro', h, 'SOSPECHOSO', 'novel_icue', 0.58) for h in hits[:4]]


def nov_rewasd(ctx):
    roots = [
        os.path.join(ctx.appdata, 'reWASD'),
        os.path.join(os.environ.get('PROGRAMFILES', ''), 'reWASD'),
    ]
    out = []
    for r in roots:
        if os.path.isdir(r):
            out.append(_issue('reWASD instalado (remap input)', r, 'SOSPECHOSO', 'novel_rewasd', 0.62))
    return out


def nov_hidusbf(ctx):
    root = os.path.join(os.environ.get('PROGRAMFILES', ''), 'HIDUSBF')
    if os.path.isdir(root):
        return [_issue('HIDUSBF (polling rate cheat mouse)', root, 'SOSPECHOSO', 'novel_hidusbf', 0.7)]
    return []


def nov_overwolf(ctx):
    root = os.path.join(ctx.appdata, 'Overwolf')
    if not os.path.isdir(root):
        return []
    hits = _grep_paths(root, ('cheat', 'hack', 'vape', 'forge'), 4)
    return [_issue('Overwolf/CurseForge app', h, 'SOSPECHOSO', 'novel_overwolf', 0.55) for h in hits[:4]]


def nov_powershell_transcripts(ctx):
    root = os.path.join(ctx.userprofile, 'Documents')
    transcripts = glob.glob(os.path.join(root, '**', 'PowerShell_transcript*.txt'), recursive=True)[:8]
    out = []
    for tr in transcripts:
        t = _read_text_file(tr, 5000).lower()
        if any(c in t for c in ('vape', 'inject', 'bypass', 'minecraft', 'baritone')):
            out.append(_issue('PowerShell transcript sospechoso', tr, 'SOSPECHOSO', 'novel_ps_transcript', 0.72))
    return out


def nov_java_flight_recordings(ctx):
    root = os.path.join(ctx.userprofile)
    jfr = glob.glob(os.path.join(root, '**', '*.jfr'), recursive=True)[:5]
    return [_issue('Java Flight Recording (sesión MC)', p, 'NORMAL', 'novel_jfr', 0.4) for p in jfr]


def nov_sticky_notes_db(ctx):
    for rel in (
        r'Microsoft\Sticky Notes\plum.sqlite',
        r'Microsoft\Sticky Notes\StickyNotes.snt',
    ):
        p = os.path.join(ctx.appdata, rel)
        if os.path.isfile(p):
            return [_issue('Sticky Notes DB (notas locales)', p, 'NORMAL', 'novel_sticky', 0.35)]
    return []


def nov_windows_search_edb(ctx):
    edb = os.path.join(os.environ.get('PROGRAMDATA', ''), 'Microsoft', 'Search', 'Data', 'Applications', 'Windows', 'Windows.edb')
    if os.path.isfile(edb):
        try:
            if os.path.getmtime(edb) > time.time() - 3600:
                return [_issue('Índice Windows Search actualizado hace <1h', edb, 'NORMAL', 'novel_search', 0.35)]
        except Exception:
            pass
    return []


def nov_wsl_distros(ctx):
    root = os.path.join(ctx.userprofile, 'AppData', 'Local', 'Packages')
    if not os.path.isdir(root):
        return []
    out = []
    for name in os.listdir(root):
        if 'canonical' in name.lower() or 'wsl' in name.lower():
            out.append(_issue('WSL distro instalada', os.path.join(root, name), 'NORMAL', 'novel_wsl', 0.4))
    return out[:3]


def nov_streamlabs(ctx):
    root = os.path.join(ctx.appdata, 'slobs-client')
    if os.path.isdir(root):
        return [_issue('Streamlabs OBS instalado', root, 'NORMAL', 'novel_streamlabs', 0.35)]
    return []


def nov_voicemod_macros(ctx):
    root = os.path.join(ctx.appdata, 'Voicemod')
    if not os.path.isdir(root):
        return []
    hits = _grep_paths(root, ('macro', 'shortcut', 'bind'), 3)
    return [_issue('Voicemod binding', h, 'POCO_SOSPECHOSO', 'novel_voicemod', 0.45) for h in hits[:3]]


def nov_epic_minecraft(ctx):
    root = os.path.join(ctx.appdata, 'EpicGamesLauncher', 'Saved', 'Logs')
    if not os.path.isdir(root):
        return []
    out = []
    for lg in glob.glob(os.path.join(root, '*.log'))[:5]:
        t = _read_text_file(lg, 8000).lower()
        if 'minecraft' in t:
            out.append(_issue('Epic Launcher log menciona Minecraft', lg, 'NORMAL', 'novel_epic', 0.4))
    return out


def nov_automatic_destinations(ctx):
    """Jump Lists Automatic Destinations — distinto al jump list de main."""
    base = os.path.join(ctx.appdata, r'Microsoft\Windows\Recent\AutomaticDestinations')
    if not os.path.isdir(base):
        return []
    recent = sorted(glob.glob(os.path.join(base, '*')))[-12:]
    out = []
    for p in recent:
        try:
            if os.path.getmtime(p) > time.time() - 86400 * 3:
                out.append(_issue('Jump List reciente (AutomaticDestinations)', p, 'POCO_SOSPECHOSO',
                                  'novel_jumplist', 0.48))
        except Exception:
            pass
    return out[:5]


def nov_custom_destinations(ctx):
    base = os.path.join(ctx.appdata, r'Microsoft\Windows\Recent\CustomDestinations')
    if not os.path.isdir(base):
        return []
    return [_issue('CustomDestinations jump list', base, 'NORMAL', 'novel_customjump', 0.35)]


def nov_zone_identifier(ctx):
    """Archivos descargados de internet (Zone.Identifier ADS)."""
    dl = ctx.downloads
    if not dl or not os.path.isdir(dl):
        return []
    out = []
    for fn in os.listdir(dl)[:40]:
        if not fn.lower().endswith(('.jar', '.exe', '.zip', '.rar')):
            continue
        fp = os.path.join(dl, fn)
        ads = fp + ':Zone.Identifier'
        try:
            if os.path.isfile(ads) or 'zone' in str(fn).lower():
                low = fn.lower()
                if any(c in low for c in ('vape', 'cheat', 'hack', 'client', 'forge')):
                    out.append(_issue('Descarga marcada Zone.Identifier', fp, 'SOSPECHOSO',
                                      'novel_zoneid', 0.7))
        except Exception:
            pass
    return out[:6]


def nov_minecraft_launcher_log(ctx):
    """launcher_log.txt / latest.log distinto al scan de logs genérico."""
    mc = ctx.minecraft_root
    if not mc:
        return []
    out = []
    for name in ('launcher_log.txt', 'launcher_log.archived.log'):
        p = os.path.join(mc, name)
        if os.path.isfile(p):
            t = _read_text_file(p, 10000).lower()
            if any(c in t for c in ('cheat', 'hack', 'inject', 'unauthorized', 'mod')):
                out.append(_issue(f'Launcher log sospechoso: {name}', p, 'SOSPECHOSO', 'novel_launcher_log', 0.7))
    return out


_CUSTOM_SPECS = [
    ('nov_timeline', 'Windows Timeline ActivitiesCache', nov_windows_timeline),
    ('nov_lunar', 'Lunar Client artefactos', nov_lunar_client),
    ('nov_feather', 'Feather Launcher', nov_feather_client),
    ('nov_prism', 'Prism / PolyMC instancias', nov_prism_launcher),
    ('nov_sharex', 'ShareX History', nov_sharex_history),
    ('nov_medal', 'Medal.tv clips', nov_medal_tv),
    ('nov_anydesk', 'AnyDesk traces', nov_anydesk_traces),
    ('nov_teamviewer', 'TeamViewer logs', nov_teamviewer),
    ('nov_rustdesk', 'RustDesk', nov_rustdesk),
    ('nov_bedrock', 'Minecraft Bedrock package', nov_minecraft_bedrock),
    ('nov_xbox', 'Xbox Game Bar', nov_xbox_game_bar),
    ('nov_nvidia', 'GeForce Experience logs', nov_geforce_experience),
    ('nov_ghub', 'Logitech G HUB macros', nov_logitech_ghub),
    ('nov_steelseries', 'SteelSeries GG', nov_steelseries_gg),
    ('nov_icue', 'Corsair iCUE', nov_corsair_icue),
    ('nov_rewasd', 'reWASD remap', nov_rewasd),
    ('nov_hidusbf', 'HIDUSBF mouse polling', nov_hidusbf),
    ('nov_overwolf', 'Overwolf / CurseForge', nov_overwolf),
    ('nov_ps_transcript', 'PowerShell transcripts', nov_powershell_transcripts),
    ('nov_jfr', 'Java Flight Recordings', nov_java_flight_recordings),
    ('nov_sticky', 'Sticky Notes DB', nov_sticky_notes_db),
    ('nov_search', 'Windows Search index', nov_windows_search_edb),
    ('nov_wsl', 'WSL distros', nov_wsl_distros),
    ('nov_streamlabs', 'Streamlabs', nov_streamlabs),
    ('nov_voicemod', 'Voicemod', nov_voicemod_macros),
    ('nov_epic', 'Epic + Minecraft', nov_epic_minecraft),
    ('nov_jumplist_auto', 'Jump Lists AutomaticDestinations', nov_automatic_destinations),
    ('nov_jumplist_custom', 'Jump Lists CustomDestinations', nov_custom_destinations),
    ('nov_zoneid', 'Zone.Identifier descargas', nov_zone_identifier),
    ('nov_launcher_log', 'launcher_log.txt', nov_minecraft_launcher_log),
]

# ── Registro final ───────────────────────────────────────────────────────────

NOVEL_MODULES = []
for mod_id, label, mod_path, fn_name in _SCANNER_SPECS:
    NOVEL_MODULES.append((mod_id, label, _make_pkg_module(mod_id, label, mod_path, fn_name)))
for mod_id, label, method in _FORENSIC_SPECS:
    NOVEL_MODULES.append((mod_id, label, _make_forensic_module(mod_id, label, method)))
for mod_id, label, fn in _CUSTOM_SPECS:
    NOVEL_MODULES.append((mod_id, label, fn))
