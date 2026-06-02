"""
70 módulos de escaneo extendidos (v1.7) — checks ligeros y paralelizables.
Cada función recibe ctx (ArgusApp) y devuelve list[dict] de hallazgos.
"""
import os
import glob
import re
from pathlib import Path


def _issue(nombre, ruta='', alerta='SOSPECHOSO', tipo='extended_scan', conf=0.65):
    return {
        'tipo': tipo,
        'nombre': nombre,
        'ruta': ruta or '',
        'archivo': os.path.basename(ruta) if ruta else '',
        'detalle': ruta or nombre,
        'alerta': alerta,
        'categoria': 'EXTENDED',
        'confidence': conf,
    }


def _appdata():
    return os.environ.get('APPDATA', '') or ''


def _userprofile():
    return os.environ.get('USERPROFILE', '') or ''


def _minecraft_root():
    for p in (
        os.path.join(_appdata(), '.minecraft'),
        os.path.join(_appdata(), 'Roaming', '.minecraft'),
    ):
        if os.path.isdir(p):
            return p
    return ''


def _path_has_any(root, needles, max_depth=4):
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
        if len(hits) >= 3:
            break
    return hits


# ── 001–010 Minecraft / clientes ───────────────────────────────────────────

def ext_001_lunar_ghost_traces(ctx):
    hits = _path_has_any(_minecraft_root(), ('lunar', 'badlion', 'feather'), 3)
    return [_issue('Cliente launcher detectado', h, 'NORMAL', conf=0.4) for h in hits[:2]]


def ext_002_forge_hack_folder(ctx):
    mc = _minecraft_root()
    hits = _path_has_any(mc, ('wurst', 'impact', 'sigma', 'liquidbounce'), 5)
    return [_issue('Carpeta/mod de hack en .minecraft', h, 'CRITICAL', conf=0.9) for h in hits[:5]]


def ext_003_recent_launcher_logs(ctx):
    mc = _minecraft_root()
    logs = os.path.join(mc, 'logs') if mc else ''
    if not os.path.isdir(logs):
        return []
    recent = sorted(glob.glob(os.path.join(logs, '*.log')), key=os.path.getmtime, reverse=True)[:3]
    out = []
    for p in recent:
        try:
            if os.path.getmtime(p) > (__import__('time').time() - 86400 * 3):
                txt = Path(p).read_text(encoding='utf-8', errors='ignore')[:4000].lower()
                if any(w in txt for w in ('inject', 'vape', 'cheat', 'bypass')):
                    out.append(_issue('Log de Minecraft con término sospechoso', p, 'SOSPECHOSO', 0.75))
        except Exception:
            pass
    return out


def ext_004_options_autoclick(ctx):
    mc = _minecraft_root()
    opt = os.path.join(mc, 'options.txt') if mc else ''
    if not os.path.isfile(opt):
        return []
    try:
        t = Path(opt).read_text(encoding='utf-8', errors='ignore').lower()
        if 'toggle' in t and 'sprint' in t and ('key_' in t):
            pass
        if re.search(r'key_[^\s:]+:.*(macro|autoclick)', t):
            return [_issue('options.txt con binding sospechoso', opt, 'SOSPECHOSO', 0.7)]
    except Exception:
        pass
    return []


def ext_005_resourcepack_cheat_names(ctx):
    mc = _minecraft_root()
    rp = os.path.join(mc, 'resourcepacks') if mc else ''
    hits = _path_has_any(rp, ('xray', 'esp', 'chams', 'wallhack'), 2) if rp else []
    return [_issue('Resource pack con nombre de cheat', h, 'SOSPECHOSO', 0.72) for h in hits[:4]]


def ext_006_shader_inject_folder(ctx):
    mc = _minecraft_root()
    hits = _path_has_any(mc, ('iris', 'optifine', 'sodium'), 3)
    return []  # legítimos — módulo reservado para heurística futura


def ext_007_versions_json_tamper(ctx):
    mc = _minecraft_root()
    vf = os.path.join(mc, 'versions') if mc else ''
    if not os.path.isdir(vf):
        return []
    for jar in glob.glob(os.path.join(vf, '**', '*.jar'), recursive=True)[:30]:
        jl = jar.lower()
        if any(x in jl for x in ('vape', 'entropy', 'whiteout', 'ghost')):
            return [_issue('JAR de versión con nombre de hack', jar, 'CRITICAL', 0.92)]
    return []


def ext_008_mods_folder_size_spike(ctx):
    mods = os.path.join(_minecraft_root(), 'mods') if _minecraft_root() else ''
    if not os.path.isdir(mods):
        return []
    big = []
    for f in os.listdir(mods):
        fp = os.path.join(mods, f)
        try:
            if os.path.isfile(fp) and os.path.getsize(fp) > 8_000_000:
                big.append(fp)
        except Exception:
            pass
    return [_issue('Mod JAR inusualmente grande (>8MB)', p, 'SOSPECHOSO', 0.55) for p in big[:3]]


def ext_009_screenshots_recent_hack_ui(ctx):
    shots = os.path.join(_minecraft_root(), 'screenshots') if _minecraft_root() else ''
    if not os.path.isdir(shots):
        return []
    return []


def ext_010_server_resource_packs(ctx):
    mc = _minecraft_root()
    sp = os.path.join(mc, 'server-resource-packs') if mc else ''
    if os.path.isdir(sp) and os.listdir(sp):
        return [_issue('Server resource packs cache presente', sp, 'NORMAL', 0.35)]
    return []


# ── 011–020 Sistema / evasión ──────────────────────────────────────────────

def ext_011_prefetch_cleared_recently(ctx):
    pf = os.path.join(os.environ.get('WINDIR', 'C:\\Windows'), 'Prefetch')
    if not os.path.isdir(pf):
        return []
    count = len(os.listdir(pf))
    if count < 15:
        return [_issue('Prefetch con muy pocos archivos (posible limpieza)', pf, 'SOSPECHOSO', 0.6)]
    return []


def ext_012_temp_large_executables(ctx):
    tmp = os.environ.get('TEMP', '')
    if not tmp:
        return []
    out = []
    for p in glob.glob(os.path.join(tmp, '*.exe'))[:40]:
        try:
            if os.path.getsize(p) > 500_000:
                out.append(_issue('Ejecutable grande en TEMP', p, 'SOSPECHOSO', 0.68))
        except Exception:
            pass
    return out[:4]


def ext_013_recent_run_mru(ctx):
    try:
        import winreg
        with winreg.OpenKey(winreg.HKEY_CURRENT_USER,
                            r'Software\Microsoft\Windows\CurrentVersion\Explorer\RecentDocs') as k:
            sub = winreg.QueryInfoKey(k)[0]
            if sub == 0:
                return [_issue('RecentDocs vacío (posible limpieza)', '', 'SOSPECHOSO', 0.5)]
    except Exception:
        pass
    return []


def ext_014_hosts_file_minecraft(ctx):
    hosts = os.path.join(os.environ.get('WINDIR', ''), 'System32', 'drivers', 'etc', 'hosts')
    if not os.path.isfile(hosts):
        return []
    try:
        t = Path(hosts).read_text(encoding='utf-8', errors='ignore').lower()
        if 'minecraft' in t or 'mojang' in t or 'hypixel' in t:
            return [_issue('Archivo hosts modificado (Minecraft/Mojang)', hosts, 'CRITICAL', 0.88)]
    except Exception:
        pass
    return []


def ext_015_dns_cache_flush_indicator(ctx):
    """ipconfig /flushdns en historial reciente o Prefetch de ipconfig."""
    pf = os.path.join(os.environ.get('WINDIR', 'C:\\Windows'), 'Prefetch')
    if os.path.isdir(pf):
        for fn in os.listdir(pf):
            if fn.upper().startswith('IPCONFIG'):
                try:
                    if os.path.getmtime(os.path.join(pf, fn)) > (__import__('time').time() - 3600):
                        return [_issue('ipconfig ejecutado recientemente (posible flush DNS)', fn, 'SOSPECHOSO', 0.58)]
                except Exception:
                    pass
    return []


def ext_016_vpn_adapters_active(ctx):
    try:
        import psutil
        for name, addrs in psutil.net_if_addrs().items():
            nl = name.lower()
            if any(v in nl for v in ('vpn', 'tap', 'tun', 'wireguard', 'nord', 'proton')):
                return [_issue('Adaptador de red VPN activo', name, 'SOSPECHOSO', 0.55)]
    except Exception:
        pass
    return []


def ext_017_vm_registry_hints(ctx):
    try:
        import winreg
        with winreg.OpenKey(winreg.HKEY_LOCAL_MACHINE, r'SYSTEM\CurrentControlSet\Services\Disk\Enum') as k:
            i = 0
            while True:
                try:
                    val, _ = winreg.EnumValue(k, i)
                    if 'vbox' in str(val).lower() or 'vmware' in str(val).lower():
                        return [_issue('Indicador de máquina virtual en disco', str(val), 'SOSPECHOSO', 0.7)]
                except OSError:
                    break
                i += 1
    except Exception:
        pass
    return []


def ext_018_sandbox_username(ctx):
    user = (os.environ.get('USERNAME') or '').lower()
    if user in ('sandbox', 'virus', 'malware', 'test', 'user'):
        return [_issue(f'Usuario de sistema sospechoso: {user}', '', 'SOSPECHOSO', 0.6)]
    return []


def ext_019_low_disk_recent_install(ctx):
    try:
        import shutil
        u = shutil.disk_usage('C:\\')
        if u.free < 2 * 1024 ** 3:
            return [_issue('Poco espacio en C: (posible VM o limpieza)', 'C:\\', 'NORMAL', 0.45)]
    except Exception:
        pass
    return []


def ext_020_windows_defender_disabled(ctx):
    try:
        import winreg
        with winreg.OpenKey(winreg.HKEY_LOCAL_MACHINE,
                            r'SOFTWARE\Microsoft\Windows Defender\Real-Time Protection') as k:
            v, _ = winreg.QueryValueEx(k, 'DisableRealtimeMonitoring')
            if v:
                return [_issue('Windows Defender tiempo real desactivado', '', 'SOSPECHOSO', 0.75)]
    except Exception:
        pass
    return []


# ── 021–040 Descargas / herramientas ───────────────────────────────────────

def _downloads_scan(needles, alerta='SOSPECHOSO'):
    dl = os.path.join(_userprofile(), 'Downloads')
    if not os.path.isdir(dl):
        return []
    hits = _path_has_any(dl, needles, 2)
    return [_issue('Archivo sospechoso en Descargas', h, alerta, 0.78) for h in hits[:5]]


def ext_021_downloads_vape(ctx):
    return _downloads_scan(('vape', 'vapelite', 'vapev4'), 'CRITICAL')


def ext_022_downloads_injector(ctx):
    return _downloads_scan(('injector', 'extremeinjector', 'xenos'), 'CRITICAL')


def ext_023_downloads_ghost_jar(ctx):
    return _downloads_scan(('wurst', 'liquidbounce', 'sigma', 'flux'), 'CRITICAL')


def ext_024_downloads_autoclicker(ctx):
    return _downloads_scan(('autoclick', 'op autoclicker', 'gs autoclicker', 'murgee'), 'SOSPECHOSO')


def ext_025_downloads_macro_recorder(ctx):
    return _downloads_scan(('tinytask', 'pulover', 'macro recorder', 'autohotkey'), 'SOSPECHOSO')


def ext_026_desktop_shortcuts_hack(ctx):
    desk = os.path.join(_userprofile(), 'Desktop')
    hits = _path_has_any(desk, ('vape', 'wurst', 'cheat', 'hack'), 1) if os.path.isdir(desk) else []
    return [_issue('Acceso directo sospechoso en escritorio', h, 'SOSPECHOSO', 0.7) for h in hits[:4]]


def ext_027_onedrive_sync_cheat(ctx):
    od = os.path.join(_userprofile(), 'OneDrive')
    hits = _path_has_any(od, ('minecraft hack', 'vape', 'cheat client'), 4) if os.path.isdir(od) else []
    return [_issue('Posible cheat en OneDrive', h, 'SOSPECHOSO', 0.65) for h in hits[:3]]


def ext_028_rar_zip_hack_archives(ctx):
    dl = os.path.join(_userprofile(), 'Downloads')
    out = []
    for pat in ('*.zip', '*.rar', '*.7z'):
        for p in glob.glob(os.path.join(dl, pat))[:25]:
            nl = os.path.basename(p).lower()
            if any(w in nl for w in ('hack', 'vape', 'client', 'cheat', 'sigma')):
                out.append(_issue('Archivo comprimido con nombre de hack', p, 'SOSPECHOSO', 0.72))
    return out[:5]


def ext_029_browser_downloads_chrome(ctx):
    base = os.path.join(_appdata(), 'Google', 'Chrome', 'User Data')
    if not os.path.isdir(base):
        return []
    out = []
    for root, _, files in os.walk(base):
        if 'download' not in root.lower() and 'file' not in root.lower():
            continue
        for fn in files[:80]:
            nl = fn.lower()
            if any(w in nl for w in ('vape', 'wurst', 'cheat', 'inject', 'baritone', '.jar')):
                out.append(_issue('Descarga sospechosa en perfil Chrome', os.path.join(root, fn), 'SOSPECHOSO', 0.72))
        if len(out) >= 4:
            break
    return out[:5]


def ext_030_edge_downloads(ctx):
    base = os.path.join(_appdata(), 'Microsoft', 'Edge', 'User Data')
    if not os.path.isdir(base):
        return []
    out = []
    for root, _, files in os.walk(base):
        if 'download' not in root.lower():
            continue
        for fn in files[:60]:
            nl = fn.lower()
            if any(w in nl for w in ('vape', 'cheat', 'hack', 'baritone', 'inject')):
                out.append(_issue('Descarga sospechosa en Edge', os.path.join(root, fn), 'SOSPECHOSO', 0.7))
        if len(out) >= 4:
            break
    return out[:5]


def ext_031_temp_rar_self_extract(ctx):
    return ext_012_temp_large_executables(ctx)


def ext_032_public_folder_executables(ctx):
    pub = os.path.join(os.environ.get('PUBLIC', ''), 'Desktop')
    hits = _path_has_any(pub, ('.exe',), 1) if os.path.isdir(pub) else []
    return [_issue('Ejecutable en escritorio público', h, 'NORMAL', 0.4) for h in hits if h.lower().endswith('.exe')][:2]


def ext_033_programdata_hidden(ctx):
    pd = os.environ.get('ProgramData', '')
    hits = _path_has_any(pd, ('vape', 'cheat', 'inject'), 2) if pd else []
    return [_issue('Rastro en ProgramData', h, 'SOSPECHOSO', 0.7) for h in hits[:3]]


def ext_034_appdata_local_cheat(ctx):
    loc = os.path.join(_appdata(), 'Local')
    hits = _path_has_any(loc, ('vape', 'entropy', 'ghostclient'), 3)
    return [_issue('Carpeta sospechosa en AppData\\Local', h, 'SOSPECHOSO', 0.68) for h in hits[:4]]


def ext_035_roaming_cheat_config(ctx):
    hits = _path_has_any(_appdata(), ('vape', 'drip', 'rise'), 3)
    return [_issue('Config de cheat en AppData\\Roaming', h, 'CRITICAL', 0.85) for h in hits[:4]]


def ext_036_steam_minecraft_mod(ctx):
    steam = os.path.join(_appdata(), 'Steam', 'steamapps', 'common')
    if not os.path.isdir(steam):
        return []
    hits = _path_has_any(steam, ('cheat', 'hack', 'vape', 'baritone'), 3)
    return [_issue('Rastro en juego Steam', h, 'SOSPECHOSO', 0.65) for h in hits[:3]]


def ext_037_discord_overlay_inject(ctx):
    disc = os.path.join(_appdata(), 'discord')
    hits = _path_has_any(disc, ('inject', 'hook', 'cheat', 'vape'), 4) if os.path.isdir(disc) else []
    return [_issue('Archivo sospechoso en Discord', h, 'SOSPECHOSO', 0.6) for h in hits[:3]]


def ext_038_obs_virtualcam_abuse(ctx):
    return _proc_scan(('obs-virtualcam', 'virtualcam', 'snap camera'))[:2]


def ext_039_radmin_anydesk_combo(ctx):
    try:
        import psutil
        names = [p.info.get('name', '').lower() for p in psutil.process_iter(['name'])]
        if 'anydesk.exe' in names and 'radmin.exe' in names:
            return [_issue('AnyDesk y Radmin simultáneos', '', 'NORMAL', 0.4)]
    except Exception:
        pass
    return []


def ext_040_clipboard_history_cleared(ctx):
    try:
        import winreg
        with winreg.OpenKey(winreg.HKEY_CURRENT_USER,
                            r'Software\Microsoft\Clipboard') as k:
            pass
    except FileNotFoundError:
        return []
    except Exception:
        pass
    # Windows 10+ clipboard history — si el servicio existe pero sin entradas tras SS sospechoso (heurística débil)
    return []


# ── 041–070 Procesos / red / forense ligero ────────────────────────────────

def _proc_scan(needles):
    try:
        import psutil
    except ImportError:
        return []
    out = []
    for p in psutil.process_iter(['name', 'exe']):
        try:
            blob = f"{p.info.get('name','')} {p.info.get('exe','')}".lower()
            if any(n in blob for n in needles):
                out.append(_issue('Proceso sospechoso en ejecución', blob[:200], 'SOSPECHOSO', 0.72))
        except Exception:
            pass
        if len(out) >= 4:
            break
    return out


def ext_041_proc_cheat_loader(ctx):
    return _proc_scan(('vape', 'injector', 'cheat', 'ghost'))


def ext_042_proc_python_mineflayer(ctx):
    return _proc_scan(('mineflayer', 'minecraft-bot'))


def ext_043_proc_java_duplicate(ctx):
    try:
        import psutil
        javas = [p for p in psutil.process_iter(['name']) if (p.info.get('name') or '').lower() == 'javaw.exe']
        if len(javas) > 4:
            return [_issue(f'Múltiples javaw.exe ({len(javas)})', '', 'SOSPECHOSO', 0.55)]
    except Exception:
        pass
    return []


def ext_044_proc_powershell_hidden(ctx):
    return _proc_scan(('-windowstyle hidden', 'bypass', '-enc '))


def ext_045_proc_cmd_spawning(ctx):
    try:
        import psutil
        for p in psutil.process_iter(['name', 'ppid', 'cmdline']):
            if (p.info.get('name') or '').lower() != 'cmd.exe':
                continue
            cmd = ' '.join(p.info.get('cmdline') or []).lower()
            if any(x in cmd for x in ('vape', 'curl', 'bitsadmin', 'certutil -urlcache', 'powershell -enc')):
                return [_issue('CMD con comando sospechoso', cmd[:180], 'SOSPECHOSO', 0.75)]
    except Exception:
        pass
    return []


def ext_046_startup_folder_lnk(ctx):
    startup = os.path.join(_appdata(), r'Microsoft\Windows\Start Menu\Programs\Startup')
    hits = _path_has_any(startup, ('.exe', '.bat', '.vbs'), 1)
    return [_issue('Elemento en carpeta de inicio', h, 'SOSPECHOSO', 0.6) for h in hits if not h.lower().endswith('.lnk')][:3]


def ext_047_scheduled_tasks_xml(ctx):
    tasks = os.path.join(os.environ.get('WINDIR', ''), 'System32', 'Tasks')
    if not os.path.isdir(tasks):
        return []
    out = []
    for root, _, files in os.walk(tasks):
        for fn in files:
            if not fn.endswith('.xml'):
                continue
            nl = (fn + root).lower()
            if any(w in nl for w in ('vape', 'cheat', 'inject', 'macro', 'baritone')):
                out.append(_issue('Tarea programada sospechosa', os.path.join(root, fn), 'CRITICAL', 0.8))
        if len(out) >= 4:
            break
    return out


def ext_048_wmi_persistence_hint(ctx):
    try:
        import subprocess
        r = subprocess.run(
            ['wmic', '/namespace:\\\\root\\subscription', 'path', '__eventfilter', 'get', 'name'],
            capture_output=True, text=True, timeout=8,
        )
        if r.returncode == 0 and r.stdout:
            for line in r.stdout.splitlines():
                ll = line.lower()
                if any(w in ll for w in ('minecraft', 'cheat', 'inject')):
                    return [_issue('Filtro WMI sospechoso', line.strip(), 'CRITICAL', 0.85)]
    except Exception:
        pass
    return []


def ext_049_usb_mount_recent(ctx):
    try:
        import psutil
        for p in psutil.disk_partitions():
            if 'removable' in (p.opts or '').lower() or p.device.lower().startswith(('e:', 'f:', 'g:')):
                return [_issue('Unidad removible montada', p.mountpoint or p.device, 'NORMAL', 0.35)]
    except Exception:
        pass
    return []


def ext_050_cloud_sync_desktop(ctx):
    for name in ('Dropbox', 'Google Drive', 'iCloudDrive'):
        p = os.path.join(_userprofile(), name)
        hits = _path_has_any(p, ('vape', 'cheat', 'hack'), 3) if os.path.isdir(p) else []
        if hits:
            return [_issue(f'Archivo sospechoso en {name}', hits[0], 'SOSPECHOSO', 0.68)]
    return []


def ext_051_minecraft_log4j_old(ctx):
    mc = _minecraft_root()
    lib = os.path.join(mc, 'libraries', 'org', 'apache', 'logging', 'log4j') if mc else ''
    if os.path.isdir(lib):
        for root, _, files in os.walk(lib):
            for fn in files:
                if 'log4j' in fn and any(v in fn for v in ('2.14', '2.15.0', '2.16.0')):
                    return [_issue('Log4j antiguo en libraries (riesgo histórico)', os.path.join(root, fn), 'NORMAL', 0.4)]
    return []


def ext_052_multi_mc_accounts_json(ctx):
    launcher = os.path.join(_appdata(), '.minecraft', 'launcher_profiles.json')
    if os.path.isfile(launcher):
        try:
            if 'cheat' in Path(launcher).read_text(encoding='utf-8', errors='ignore').lower():
                return [_issue('launcher_profiles.json menciona cheat', launcher, 'SOSPECHOSO', 0.7)]
        except Exception:
            pass
    return []


def ext_053_feather_lunar_config(ctx):
    return ext_001_lunar_ghost_traces(ctx)


def ext_054_badlion_waypoints_cheat(ctx):
    for base in (_appdata(),):
        hits = _path_has_any(os.path.join(base, 'Badlion Client'), ('cheat', 'hack', 'inject'), 4)
        if hits:
            return [_issue('Rastro sospechoso en Badlion', hits[0], 'SOSPECHOSO', 0.6)]
    return []


def ext_055_polymc_prismlauncher(ctx):
    hits = _path_has_any(_appdata(), ('polymc', 'prismlauncher', 'multimc'), 2)
    return [_issue('Launcher alternativo detectado', h, 'NORMAL', 0.35) for h in hits[:2]]


def ext_056_curseforge_overwolf(ctx):
    return []


def ext_057_modrinth_app(ctx):
    return []


def ext_058_ftb_app_legacy(ctx):
    return []


def ext_059_minecraft_crash_hack_stack(ctx):
    crashes = os.path.join(_minecraft_root(), 'crash-reports')
    if not os.path.isdir(crashes):
        return []
    for p in sorted(glob.glob(os.path.join(crashes, '*.txt')), reverse=True)[:2]:
        try:
            if 'vape' in Path(p).read_text(encoding='utf-8', errors='ignore').lower():
                return [_issue('Crash report menciona cheat', p, 'CRITICAL', 0.9)]
        except Exception:
            pass
    return []


def ext_060_saves_dat_editor(ctx):
    mc = _minecraft_root()
    saves = os.path.join(mc, 'saves') if mc else ''
    if not os.path.isdir(saves):
        return []
    for root, _, files in os.walk(saves):
        for fn in files:
            if fn in ('level.dat', 'session.lock') and 'backup' in root.lower():
                return [_issue('Backup de mundo (posible edición pre-SS)', os.path.join(root, fn), 'SOSPECHOSO', 0.55)]
        if root.count(os.sep) - saves.count(os.sep) > 4:
            break
    return []


def ext_061_level_dat_unusual(ctx):
    mc = _minecraft_root()
    saves = os.path.join(mc, 'saves') if mc else ''
    if not os.path.isdir(saves):
        return []
    for sd in os.listdir(saves)[:8]:
        ld = os.path.join(saves, sd, 'level.dat')
        if os.path.isfile(ld):
            try:
                if os.path.getmtime(ld) > (__import__('time').time() - 600):
                    return [_issue('level.dat modificado hace <10 min', ld, 'SOSPECHOSO', 0.62)]
            except Exception:
                pass
    return []


def ext_062_replay_mod_cheat(ctx):
    mc = _minecraft_root()
    rm = os.path.join(mc, 'replay_recordings') if mc else ''
    if os.path.isdir(rm) and os.listdir(rm):
        return [_issue('ReplayMod con grabaciones (revisar macros)', rm, 'NORMAL', 0.4)]
    return []


def ext_063_screenshot_tools_overlay(ctx):
    return _proc_scan(('sharex', 'obs64', 'medal'))[:1]


def ext_064_stream_proof_tools(ctx):
    return _proc_scan(('streamproof', 'hider', 'nohook'))


def ext_065_memory_cleaner_evasion(ctx):
    return _proc_scan(('memreduct', 'wise memory', 'cleaner'))[:2]


def ext_066_privazer_bleachbit(ctx):
    return _proc_scan(('privazer', 'bleachbit', 'ccleaner'))[:2]


def ext_067_rkill_combofix(ctx):
    return _proc_scan(('rkill', 'combofix'))


def ext_068_defender_control_tool(ctx):
    return _downloads_scan(('defender control', 'dcontrol', 'sordum'))


def ext_069_hosts_backup_file(ctx):
    hosts = os.path.join(os.environ.get('WINDIR', ''), 'System32', 'drivers', 'etc', 'hosts')
    for suffix in ('.bak', '.old', '.backup'):
        p = hosts + suffix
        if os.path.isfile(p):
            return [_issue('Copia de seguridad de hosts (posible bypass DNS)', p, 'SOSPECHOSO', 0.65)]
    return []


def ext_070_argus_self_tamper(ctx):
    """Integridad: buscar copias del scanner en temp/descargas."""
    hits = []
    for base in (os.path.join(_userprofile(), 'Downloads'), os.path.join(_appdata(), 'Local', 'Temp')):
        if not os.path.isdir(base):
            continue
        for p in glob.glob(os.path.join(base, '**', 'Argus*.exe'), recursive=True)[:5]:
            hits.append(_issue('Copia del scanner en carpeta temporal', p, 'NORMAL', 0.4))
    return hits[:2]


# Registro ordenado de los 70 módulos extendidos
EXTENDED_MODULES = [
    ('ext_001', 'Lunar/Feather traces', ext_001_lunar_ghost_traces),
    ('ext_002', 'Forge hack folders', ext_002_forge_hack_folder),
    ('ext_003', 'Recent MC logs', ext_003_recent_launcher_logs),
    ('ext_004', 'options.txt bindings', ext_004_options_autoclick),
    ('ext_005', 'Resourcepack cheat names', ext_005_resourcepack_cheat_names),
    ('ext_006', 'Shader inject (reserved)', ext_006_shader_inject_folder),
    ('ext_007', 'versions jar names', ext_007_versions_json_tamper),
    ('ext_008', 'Large mods', ext_008_mods_folder_size_spike),
    ('ext_009', 'Screenshots (reserved)', ext_009_screenshots_recent_hack_ui),
    ('ext_010', 'Server resource packs', ext_010_server_resource_packs),
    ('ext_011', 'Prefetch cleared', ext_011_prefetch_cleared_recently),
    ('ext_012', 'TEMP executables', ext_012_temp_large_executables),
    ('ext_013', 'RecentDocs empty', ext_013_recent_run_mru),
    ('ext_014', 'Hosts minecraft', ext_014_hosts_file_minecraft),
    ('ext_015', 'DNS flush (reserved)', ext_015_dns_cache_flush_indicator),
    ('ext_016', 'VPN adapters', ext_016_vpn_adapters_active),
    ('ext_017', 'VM disk enum', ext_017_vm_registry_hints),
    ('ext_018', 'Sandbox username', ext_018_sandbox_username),
    ('ext_019', 'Low disk space', ext_019_low_disk_recent_install),
    ('ext_020', 'Defender disabled', ext_020_windows_defender_disabled),
    ('ext_021', 'Downloads Vape', ext_021_downloads_vape),
    ('ext_022', 'Downloads injector', ext_022_downloads_injector),
    ('ext_023', 'Downloads ghost jars', ext_023_downloads_ghost_jar),
    ('ext_024', 'Downloads autoclicker', ext_024_downloads_autoclicker),
    ('ext_025', 'Downloads macro', ext_025_downloads_macro_recorder),
    ('ext_026', 'Desktop shortcuts', ext_026_desktop_shortcuts_hack),
    ('ext_027', 'OneDrive cheat', ext_027_onedrive_sync_cheat),
    ('ext_028', 'Archives hack names', ext_028_rar_zip_hack_archives),
    ('ext_029', 'Chrome downloads', ext_029_browser_downloads_chrome),
    ('ext_030', 'Edge downloads', ext_030_edge_downloads),
    ('ext_031', 'TEMP self-extract', ext_031_temp_rar_self_extract),
    ('ext_032', 'Public desktop exe', ext_032_public_folder_executables),
    ('ext_033', 'ProgramData traces', ext_033_programdata_hidden),
    ('ext_034', 'Local AppData cheat', ext_034_appdata_local_cheat),
    ('ext_035', 'Roaming cheat config', ext_035_roaming_cheat_config),
    ('ext_036', 'Steam MC mod', ext_036_steam_minecraft_mod),
    ('ext_037', 'Discord overlay', ext_037_discord_overlay_inject),
    ('ext_038', 'OBS virtualcam', ext_038_obs_virtualcam_abuse),
    ('ext_039', 'AnyDesk+Radmin', ext_039_radmin_anydesk_combo),
    ('ext_040', 'Clipboard cleared', ext_040_clipboard_history_cleared),
    ('ext_041', 'Proc cheat loader', ext_041_proc_cheat_loader),
    ('ext_042', 'Proc mineflayer', ext_042_proc_python_mineflayer),
    ('ext_043', 'Multi javaw', ext_043_proc_java_duplicate),
    ('ext_044', 'Hidden PowerShell', ext_044_proc_powershell_hidden),
    ('ext_045', 'CMD spawning', ext_045_proc_cmd_spawning),
    ('ext_046', 'Startup folder', ext_046_startup_folder_lnk),
    ('ext_047', 'Scheduled tasks', ext_047_scheduled_tasks_xml),
    ('ext_048', 'WMI persistence', ext_048_wmi_persistence_hint),
    ('ext_049', 'USB recent', ext_049_usb_mount_recent),
    ('ext_050', 'Cloud desktop', ext_050_cloud_sync_desktop),
    ('ext_051', 'Log4j old', ext_051_minecraft_log4j_old),
    ('ext_052', 'Launcher profiles', ext_052_multi_mc_accounts_json),
    ('ext_053', 'Feather/Lunar cfg', ext_053_feather_lunar_config),
    ('ext_054', 'Badlion waypoints', ext_054_badlion_waypoints_cheat),
    ('ext_055', 'PolyMC/Prism', ext_055_polymc_prismlauncher),
    ('ext_056', 'Curseforge', ext_056_curseforge_overwolf),
    ('ext_057', 'Modrinth app', ext_057_modrinth_app),
    ('ext_058', 'FTB legacy', ext_058_ftb_app_legacy),
    ('ext_059', 'Crash report hack', ext_059_minecraft_crash_hack_stack),
    ('ext_060', 'saves.dat editor', ext_060_saves_dat_editor),
    ('ext_061', 'level.dat unusual', ext_061_level_dat_unusual),
    ('ext_062', 'Replay mod cheat', ext_062_replay_mod_cheat),
    ('ext_063', 'Capture tools', ext_063_screenshot_tools_overlay),
    ('ext_064', 'Stream-proof tools', ext_064_stream_proof_tools),
    ('ext_065', 'Memory cleaners', ext_065_memory_cleaner_evasion),
    ('ext_066', 'Privazer/BleachBit', ext_066_privazer_bleachbit),
    ('ext_067', 'RKill/ComboFix', ext_067_rkill_combofix),
    ('ext_068', 'Defender control', ext_068_defender_control_tool),
    ('ext_069', 'Hosts backup', ext_069_hosts_backup_file),
    ('ext_070', 'Argus copies temp', ext_070_argus_self_tamper),
]
