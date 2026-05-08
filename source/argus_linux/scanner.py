#!/usr/bin/env python3
"""ArgusScanner Linux — entry point principal.

Uso:
    python3 -m argus_linux --token ABC123 [--server https://asperss.onrender.com]
    python3 -m argus_linux --token ABC123 --no-screenshot --offline

Standalone (con permisos +x):
    ./scanner.py --token ABC123

Mismo contrato que el .exe Windows (POST /api/scans -> POST /api/scans/<id>/results).
Las heurísticas son nativas Linux: papelera XDG, journalctl, /proc, LD_PRELOAD,
launchers MC habituales en Linux, screenshot multi-display X11/Wayland.

Plataforma #1, #2, #3, #4, #6, #7, #8, #9, #15 del MEJORAS_180.txt.
"""

from __future__ import annotations

import argparse
import base64
import getpass
import hashlib
import json
import os
import platform
import re
import socket
import shutil
import sqlite3
import subprocess
import sys
import tempfile
import time
import uuid
from typing import Any

try:
    import urllib.request
    import urllib.error
except ImportError:  # pragma: no cover
    print("[FATAL] Python 3 requerido", file=sys.stderr)
    sys.exit(2)

SCANNER_VERSION = '1.6.45-linux1'
DEFAULT_SERVER  = 'https://asperss.onrender.com'

# ── Hack-name terms (sincronizados con Windows scanner) ─────────────────────
# Lista core de marcas/clientes de cheats conocidos. Si querés extender,
# editá esta tupla — no se cargan dinámicamente porque queremos que el
# binario sea offline-capable.
HACK_TERMS = (
    # Minecraft Java cheat clients
    'wurst', 'liquidbounce', 'meteor', 'meteorclient', 'impact', 'aristois',
    'sigma', 'sigmaclient', 'rusherhack', 'rusher', 'wolfram', 'astolfo',
    'reflex', 'drip', 'rise', 'novetus', 'inertia', 'flux', 'trolly',
    'vape', 'ghost client', 'pyro', 'salhack', 'baritone',
    # Generic hack/cheat keywords (con boundaries en el regex de match)
    'killaura', 'aimbot', 'wallhack', 'esp client', 'xray client',
    'autoclicker', 'autoclick', 'triggerbot', 'noslow', 'nofall',
    'reach hack', 'fastbreak', 'speedhack',
    # CSGO/CS2/Valorant/Rust/Apex cheat brands
    'gamesense', 'onetap', 'aimware', 'fatality', 'neverlose', 'skeet',
    'osiris', 'hyper.gg', 'ragebot', 'popflash', 'novoline',
    # Generic
    'cheat client', 'cracked client', 'private cheat', 'undetected cheat',
    'hack download',
)

# Paths donde el scanner busca activamente (relativos a $HOME)
MC_INSTANCE_PATTERNS = (
    '.minecraft',
    '.local/share/multimc/instances',
    '.local/share/PrismLauncher/instances',
    '.local/share/atlauncher/instances',
    '.local/share/gdlauncher_carbon/data/instances',
    '.var/app/org.prismlauncher.PrismLauncher/data/PrismLauncher/instances',
    '.var/app/org.polymc.PolyMC/data/PolyMC/instances',
    '.var/app/com.mojang.Minecraft/.minecraft',
    'snap/minecraft-launcher/common/.minecraft',
)

# Browsers Linux: paths típicos de history sqlite
BROWSER_HISTORY_PATHS = (
    ('Chrome',       '.config/google-chrome/Default/History'),
    ('Chromium',     '.config/chromium/Default/History'),
    ('Brave',        '.config/BraveSoftware/Brave-Browser/Default/History'),
    ('Edge',         '.config/microsoft-edge/Default/History'),
    ('Opera',        '.config/opera/History'),
    ('Vivaldi',      '.config/vivaldi/Default/History'),
    ('Yandex',       '.config/yandex-browser-beta/Default/History'),
    # Flatpak variants
    ('Chrome-Flatpak',  '.var/app/com.google.Chrome/config/google-chrome/Default/History'),
    ('Brave-Flatpak',   '.var/app/com.brave.Browser/config/BraveSoftware/Brave-Browser/Default/History'),
    ('Chromium-Flatpak','.var/app/org.chromium.Chromium/config/chromium/Default/History'),
)
FIREFOX_PROFILE_ROOTS = (
    '.mozilla/firefox',
    '.var/app/org.mozilla.firefox/.mozilla/firefox',
    'snap/firefox/common/.mozilla/firefox',
)

# DNS cheat keywords usados en browser history (mismos que el scanner Windows)
CHEAT_DOMAINS = (
    'gamesense.pub', 'onetap.com', 'onetap.su', 'aimware.net',
    'fatality.win', 'neverlose.cc', 'skeet.cc', 'osiris.cc',
    'hyper.gg', 'ragebot.fun', 'popflash.gg', 'novoline.cc',
    'wurstclient.net', 'liquidbounce.net', 'sigma-jello.com',
    'sigmaclient.net', 'rusherhack.org', 'meteorclient.com',
    'impactclient.net', 'futureclient.net', 'novetus.org',
    'inertia.club', 'flux.lol', 'trolly.gg',
)

# Mods Minecraft conocidos legítimos — no flagear
LEGIT_MC_MOD_TOKENS = (
    'optifine', 'sodium', 'lithium', 'phosphor', 'starlight', 'ferritecore',
    'iris', 'oculus', 'rubidium', 'magnesium',
    'fabric-api', 'fabric_api', 'fabricapi',
    'forge', 'neoforge', 'quilt',
    'jei', 'rei', 'roughlyenoughitems', 'justenoughitems',
    'mod-menu', 'modmenu', 'cloth-config', 'clothconfig',
    'architectury', 'shadowlib', 'kotlin-for-forge', 'fabric-language-kotlin',
    'create', 'tconstruct', 'tinkers', 'mekanism', 'thermal',
    'ae2', 'appliedenergistics', 'jourrneymap', 'journeymap', 'minimap',
    'biomes-o-plenty', 'biomesoplenty',
    'origins', 'pehkui', 'trinkets', 'curios',
    'litematica', 'tweakeroo', 'malilib',
    'replaymod', 'shaderpack', 'iris-shaders',
)

# Tools de desarrollo legítimas en Linux que vienen con .jar/.deb/.AppImage etc.
LEGIT_LINUX_DEVTOOLS = (
    'idea-iu', 'idea-ic', 'pycharm', 'webstorm', 'clion', 'goland',
    'rustrover', 'rider', 'phpstorm', 'datagrip', 'android-studio',
    'eclipse', 'netbeans', 'vscodium', 'vscode',
    'docker', 'kubectl', 'helm', 'minikube',
    'postman', 'insomnia', 'wireshark',
    'minikube', 'k3s', 'colima',
)


# ─────────────────────────── helpers ────────────────────────────────────────
def _print(msg: str) -> None:
    print(msg, flush=True)


def _is_root() -> bool:
    return hasattr(os, 'geteuid') and os.geteuid() == 0


def _smart_hack_match(text: str) -> str | None:
    """Devuelve el primer hack-term que matchea con boundaries.
    Mismo comportamiento que el Windows scanner: matchea solo cuando
    el término no está rodeado de [a-z0-9] (evita FP en compuestos)."""
    if not text:
        return None
    t = text.lower()
    for term in HACK_TERMS:
        # Boundaries: no [a-z0-9] alrededor (permite _ . - / \ etc)
        pattern = r'(?<![a-z0-9])' + re.escape(term) + r'(?![a-z0-9])'
        if re.search(pattern, t):
            return term
    return None


def _is_legit_mc_mod(filename: str) -> bool:
    if not filename:
        return False
    n = os.path.basename(filename).lower()
    return any(tok in n for tok in LEGIT_MC_MOD_TOKENS)


def _is_legit_devtool(filename_or_path: str) -> bool:
    if not filename_or_path:
        return False
    n = filename_or_path.lower()
    return any(tok in n for tok in LEGIT_LINUX_DEVTOOLS)


def _which(cmd: str) -> str | None:
    return shutil.which(cmd)


def _safe_run(cmd: list[str], timeout: int = 15) -> tuple[int, str, str]:
    """Wrapper de subprocess.run con timeout estricto."""
    try:
        r = subprocess.run(cmd, capture_output=True, text=True, timeout=timeout)
        return r.returncode, r.stdout or '', r.stderr or ''
    except subprocess.TimeoutExpired:
        return 124, '', f'timeout after {timeout}s'
    except FileNotFoundError:
        return 127, '', f'command not found: {cmd[0]}'
    except Exception as e:
        return 1, '', str(e)


def _now_ts() -> int:
    return int(time.time())


# ─────────────────────────── scanner core ───────────────────────────────────
class LinuxScanner:
    def __init__(self, token: str, server: str, *, do_screenshot: bool = True,
                 offline: bool = False, machine_name: str | None = None,
                 mc_username: str | None = None) -> None:
        self.token        = token.strip()
        self.server       = server.rstrip('/')
        self.do_screenshot = do_screenshot
        self.offline       = offline
        self.machine_name  = machine_name or socket.gethostname()
        self.mc_username   = mc_username or getpass.getuser()
        self.home          = os.path.expanduser('~')
        self.issues: list[dict[str, Any]] = []
        self.scan_id: int | None = None
        self.t_start = time.time()
        self.total_files = 0
        self.total_dirs  = 0
        self.mc_info: dict[str, Any] = {}

    # ── helper para issues ──────────────────────────────────────────────
    def _add_issue(self, *, tipo: str, nombre: str, ruta: str = '',
                   archivo: str = '', categoria: str = 'OTROS',
                   alerta: str = 'SOSPECHOSO', confidence: float = 0.5,
                   patterns: list[str] | None = None,
                   extra: dict[str, Any] | None = None) -> None:
        self.issues.append({
            'tipo':      tipo,
            'nombre':    nombre[:240],
            'ruta':      ruta[:480],
            'archivo':   archivo[:240],
            'categoria': categoria,
            'alerta':    alerta,
            'confidence': float(max(0.0, min(1.0, confidence))),
            'detected_patterns': list(patterns or []),
            'extra':     extra or {},
        })

    # ── escaneo: papelera XDG (Plataforma #3) ───────────────────────────
    def scan_xdg_trash(self) -> None:
        _print('🗑  Papelera XDG (~/.local/share/Trash/info)...')
        bases = [os.path.join(self.home, '.local', 'share', 'Trash')]
        # Trash en otras particiones: .Trash-$UID en cada mount
        try:
            uid = os.getuid()
            for line in (open('/proc/mounts').read().splitlines() if os.path.exists('/proc/mounts') else []):
                parts = line.split()
                if len(parts) >= 2:
                    mpoint = parts[1]
                    cand = os.path.join(mpoint, f'.Trash-{uid}')
                    if os.path.isdir(cand):
                        bases.append(cand)
        except Exception:
            pass

        seen = 0
        sus  = 0
        for base in bases:
            info_dir = os.path.join(base, 'info')
            files_dir = os.path.join(base, 'files')
            if not os.path.isdir(info_dir):
                continue
            try:
                entries = os.listdir(info_dir)
            except OSError:
                continue
            for entry in entries:
                if not entry.endswith('.trashinfo'):
                    continue
                seen += 1
                self.total_files += 1
                info_path = os.path.join(info_dir, entry)
                orig_path = ''
                deleted_at = ''
                try:
                    with open(info_path, 'r', encoding='utf-8', errors='ignore') as f:
                        for line in f:
                            line = line.strip()
                            if line.startswith('Path='):
                                orig_path = urllib_unquote(line[5:])
                            elif line.startswith('DeletionDate='):
                                deleted_at = line[len('DeletionDate='):]
                except OSError:
                    continue

                base_name = os.path.basename(orig_path) if orig_path else entry[:-len('.trashinfo')]
                base_l = base_name.lower()
                hack = _smart_hack_match(base_l) or _smart_hack_match(orig_path.lower())

                # Filtros anti-FP
                if not hack and _is_legit_mc_mod(base_l):
                    continue
                if not hack and _is_legit_devtool(orig_path):
                    continue
                if not hack and any(p in orig_path.lower() for p in (
                    '/.cache/', '/snap/', '/var/cache/', '/tmp/',
                    '/.local/share/Trash/',
                )):
                    continue

                ext = os.path.splitext(base_l)[1]
                interesting = ext in ('.exe', '.jar', '.dll', '.so', '.zip',
                                      '.rar', '.7z', '.appimage', '.deb', '.rpm',
                                      '.sh', '.py', '.bin')
                if not (hack or interesting):
                    continue
                sus += 1
                actual_in_files = os.path.join(files_dir, entry[:-len('.trashinfo')])
                size_b = 0
                try:
                    if os.path.exists(actual_in_files):
                        size_b = os.path.getsize(actual_in_files)
                except OSError:
                    pass

                alerta = 'CRITICAL' if hack else 'SOSPECHOSO'
                conf = 0.85 if hack else 0.45
                self._add_issue(
                    tipo='trash_xdg',
                    nombre=f'Archivo borrado (papelera XDG): {base_name}',
                    ruta=orig_path or info_path,
                    archivo=base_name,
                    categoria='ARCHIVO_BORRADO',
                    alerta=alerta,
                    confidence=conf,
                    patterns=['xdg_trash', f'ext{ext}'] + ([f'hack:{hack}'] if hack else []),
                    extra={
                        'deleted_at': deleted_at,
                        'orig_path':  orig_path,
                        'size_bytes': size_b,
                        'trash_root': base,
                        'hack_term':  hack,
                    },
                )
        _print(f'  · {seen} entries en papelera, {sus} sospechosas')

    # ── escaneo: shell history (Plataforma #4) ──────────────────────────
    def scan_shell_history(self) -> None:
        _print('📜 Historial de shells (bash/zsh/fish)...')
        targets = [
            ('bash', os.path.join(self.home, '.bash_history')),
            ('zsh',  os.path.join(self.home, '.zsh_history')),
            ('fish', os.path.join(self.home, '.local', 'share', 'fish', 'fish_history')),
        ]
        for shell, path in targets:
            if not os.path.exists(path):
                continue
            try:
                with open(path, 'r', encoding='utf-8', errors='ignore') as f:
                    content = f.read()
            except OSError:
                continue
            self.total_files += 1
            # Match por línea
            matches = []
            for ln in content.splitlines():
                ln_l = ln.lower()
                hack = _smart_hack_match(ln_l)
                if hack and not _is_legit_mc_mod(ln_l) and not _is_legit_devtool(ln_l):
                    matches.append((ln.strip()[:200], hack))
                elif any(d in ln_l for d in CHEAT_DOMAINS):
                    matches.append((ln.strip()[:200], 'cheat_domain'))
            if not matches:
                continue
            self._add_issue(
                tipo='shell_history',
                nombre=f'{shell}_history: {len(matches)} línea(s) con cheat-keyword',
                ruta=path,
                archivo=os.path.basename(path),
                categoria='EJECUCION_SHELL',
                alerta='CRITICAL',
                confidence=0.80,
                patterns=['shell_history', shell],
                extra={
                    'shell':       shell,
                    'match_count': len(matches),
                    'samples':     [{'line': l, 'kw': k} for l, k in matches[:5]],
                },
            )
        _print('  · OK')

    # ── escaneo: journalctl (Plataforma #4 cont) ────────────────────────
    def scan_journalctl_java(self) -> None:
        if not _which('journalctl'):
            return
        _print('📰 systemd-journald (java/minecraft últimas 72h)...')
        # Solo journal del usuario (no requiere sudo)
        rc, out, _err = _safe_run(
            ['journalctl', '--user', '--since', '72 hours ago',
             '-o', 'short', '--no-pager'],
            timeout=20,
        )
        if rc != 0 or not out.strip():
            return
        suspicious_lines = []
        for ln in out.splitlines():
            ln_l = ln.lower()
            if 'java' not in ln_l and 'minecraft' not in ln_l:
                continue
            hack = _smart_hack_match(ln_l)
            if hack:
                suspicious_lines.append((ln.strip()[:240], hack))
        if not suspicious_lines:
            return
        self._add_issue(
            tipo='journalctl_hack',
            nombre=f'journalctl: {len(suspicious_lines)} línea(s) sospechosas en java/minecraft',
            ruta='journalctl --user --since 72h',
            archivo='journal',
            categoria='EJECUCION',
            alerta='CRITICAL',
            confidence=0.78,
            patterns=['journalctl', 'hack_match'],
            extra={'count': len(suspicious_lines), 'samples': [
                {'line': l, 'kw': k} for l, k in suspicious_lines[:5]
            ]},
        )

    # ── escaneo: /proc procesos (Plataforma #6) ─────────────────────────
    def scan_proc_processes(self) -> None:
        _print('🔬 Procesos sospechosos (/proc)...')
        if not os.path.isdir('/proc'):
            return
        ld_preload_offenders = []
        java_with_hack_jar = []
        suspicious_cmdlines = []
        for pid_dir in os.listdir('/proc'):
            if not pid_dir.isdigit():
                continue
            pid = pid_dir
            base = f'/proc/{pid}'
            try:
                with open(f'{base}/cmdline', 'rb') as f:
                    cmdline_raw = f.read().replace(b'\x00', b' ').decode('utf-8', errors='ignore').strip()
            except OSError:
                continue
            if not cmdline_raw:
                continue
            cmd_l = cmdline_raw.lower()

            # LD_PRELOAD detection (Plataforma #6 vector clásico)
            try:
                with open(f'{base}/environ', 'rb') as f:
                    env_raw = f.read()
                for entry in env_raw.split(b'\x00'):
                    if entry.startswith(b'LD_PRELOAD='):
                        val = entry[len(b'LD_PRELOAD='):].decode('utf-8', errors='ignore')
                        if val.strip():
                            ld_preload_offenders.append({
                                'pid': int(pid), 'cmd': cmdline_raw[:200], 'preload': val[:240],
                            })
            except (OSError, PermissionError):
                pass

            # cmdline con hack-term
            hack = _smart_hack_match(cmd_l)
            if hack and not _is_legit_devtool(cmd_l) and not _is_legit_mc_mod(cmd_l):
                suspicious_cmdlines.append({'pid': int(pid), 'cmd': cmdline_raw[:240], 'hack': hack})

            # Si es java, listar maps (.jar cargados) y bibliotecas .so
            if 'java' in cmd_l and ('minecraft' in cmd_l or '-cp' in cmd_l or 'launchwrapper' in cmd_l):
                try:
                    with open(f'{base}/maps', 'r', encoding='utf-8', errors='ignore') as f:
                        for line in f:
                            # formato: addr perms offset dev inode pathname
                            parts = line.rstrip().split(None, 5)
                            if len(parts) < 6:
                                continue
                            path = parts[5]
                            path_l = path.lower()
                            if path_l.endswith('.jar') or path_l.endswith('.so'):
                                hack2 = _smart_hack_match(path_l)
                                if hack2 and not _is_legit_mc_mod(path_l):
                                    java_with_hack_jar.append({
                                        'pid': int(pid), 'jar': path, 'hack': hack2,
                                    })
                except (OSError, PermissionError):
                    pass

        if ld_preload_offenders:
            for off in ld_preload_offenders[:10]:
                self._add_issue(
                    tipo='ld_preload_active',
                    nombre=f'LD_PRELOAD activo en PID {off["pid"]}: {os.path.basename(off["preload"])[:60]}',
                    ruta='/proc/<pid>/environ',
                    archivo=off['preload'],
                    categoria='INYECCION',
                    alerta='CRITICAL',
                    confidence=0.80,
                    patterns=['ld_preload', 'injection_vector'],
                    extra=off,
                )

        if suspicious_cmdlines:
            for sc in suspicious_cmdlines[:15]:
                self._add_issue(
                    tipo='process_hack_cmdline',
                    nombre=f'Proceso PID {sc["pid"]} con hack-term: {sc["hack"]}',
                    ruta='/proc/<pid>/cmdline',
                    archivo=sc['cmd'],
                    categoria='EJECUCION',
                    alerta='CRITICAL',
                    confidence=0.85,
                    patterns=['proc_cmdline', sc['hack']],
                    extra=sc,
                )

        if java_with_hack_jar:
            for j in java_with_hack_jar[:15]:
                self._add_issue(
                    tipo='java_hack_jar_loaded',
                    nombre=f'Java PID {j["pid"]} cargó .jar sospechoso: {os.path.basename(j["jar"])}',
                    ruta='/proc/<pid>/maps',
                    archivo=j['jar'],
                    categoria='INYECCION',
                    alerta='CRITICAL',
                    confidence=0.92,
                    patterns=['java_maps', 'hack_jar', j['hack']],
                    extra=j,
                )
        _print(f'  · ld_preload={len(ld_preload_offenders)} cmdline-hack={len(suspicious_cmdlines)} java-jar={len(java_with_hack_jar)}')

    # ── escaneo: ventanas activas (Plataforma #7) ───────────────────────
    def scan_open_windows(self) -> None:
        _print('🪟 Ventanas abiertas (X11/Wayland)...')
        windows: list[str] = []
        # X11 primero (si DISPLAY está set)
        if os.environ.get('DISPLAY') and _which('wmctrl'):
            rc, out, _err = _safe_run(['wmctrl', '-l'], timeout=8)
            if rc == 0:
                for ln in out.splitlines():
                    parts = ln.split(None, 3)
                    if len(parts) >= 4:
                        windows.append(parts[3])
        # Wayland (GNOME): gdbus
        if not windows and os.environ.get('WAYLAND_DISPLAY'):
            session = (os.environ.get('XDG_CURRENT_DESKTOP') or '').lower()
            if 'gnome' in session and _which('gdbus'):
                rc, out, _err = _safe_run([
                    'gdbus', 'call', '--session',
                    '--dest', 'org.gnome.Shell',
                    '--object-path', '/org/gnome/Shell',
                    '--method', 'org.gnome.Shell.Eval',
                    'global.get_window_actors().map(a=>a.meta_window.get_title()).join("\\n")',
                ], timeout=8)
                if rc == 0:
                    # output: (true, '"title1\ntitle2"')
                    m = re.search(r"\"(.+)\"", out, re.DOTALL)
                    if m:
                        windows = [t for t in m.group(1).split('\\n') if t.strip()]
            elif 'kde' in session and _which('qdbus'):
                rc, out, _err = _safe_run(['qdbus', 'org.kde.KWin', '/KWin', 'org.kde.KWin.workspaceName'],
                                          timeout=8)
                # KDE no expone titles fácil sin scripts kwin; lo dejamos como TODO honesto

        if not windows:
            _print('  · No se pudieron listar ventanas (sin X11/wmctrl ni GNOME-Wayland)')
            return

        sus = []
        for w in windows:
            wl = w.lower()
            hack = _smart_hack_match(wl)
            if hack and not _is_legit_mc_mod(wl) and not _is_legit_devtool(wl):
                sus.append({'title': w[:200], 'hack': hack})
        for s in sus[:10]:
            self._add_issue(
                tipo='window_title_hack',
                nombre=f'Ventana abierta con hack-term: "{s["title"][:60]}"',
                ruta='wmctrl/gdbus',
                archivo=s['title'],
                categoria='EJECUCION',
                alerta='CRITICAL',
                confidence=0.78,
                patterns=['open_window', s['hack']],
                extra=s,
            )
        _print(f'  · {len(windows)} ventanas listadas, {len(sus)} sospechosas')

    # ── escaneo: launchers Minecraft (Plataforma #8) ────────────────────
    def scan_minecraft_launchers(self) -> None:
        _print('🎮 Launchers Minecraft Linux...')
        roots: list[tuple[str, str]] = []
        for pat in MC_INSTANCE_PATTERNS:
            full = os.path.join(self.home, pat)
            if os.path.isdir(full):
                roots.append((pat, full))
        if not roots:
            _print('  · No hay launchers conocidos en $HOME')
            return

        mods_collected: list[dict[str, Any]] = []
        for label, root in roots:
            for dirpath, _dirs, files in os.walk(root, followlinks=False):
                self.total_dirs += 1
                # Limitar profundidad para no explotar
                rel_depth = dirpath[len(root):].count(os.sep)
                if rel_depth > 8:
                    continue
                for fn in files:
                    if not fn.endswith('.jar'):
                        continue
                    self.total_files += 1
                    fn_l = fn.lower()
                    hack = _smart_hack_match(fn_l)
                    if not hack:
                        continue
                    if _is_legit_mc_mod(fn_l):
                        continue
                    fpath = os.path.join(dirpath, fn)
                    try:
                        size_b = os.path.getsize(fpath)
                        mtime  = os.path.getmtime(fpath)
                    except OSError:
                        size_b, mtime = 0, 0
                    digest = _sha256_file(fpath)
                    mods_collected.append({
                        'name': fn, 'path': fpath, 'size': size_b,
                        'mtime': int(mtime), 'sha256': digest, 'hack': hack,
                        'launcher_root': label,
                    })

        for m in mods_collected[:25]:
            self._add_issue(
                tipo='minecraft_hack_jar',
                nombre=f'Mod sospechoso: {m["name"]} (en {m["launcher_root"]})',
                ruta=m['path'],
                archivo=m['name'],
                categoria='MINECRAFT',
                alerta='CRITICAL',
                confidence=0.92,
                patterns=['mc_jar', m['hack']],
                extra={
                    'sha256':   m['sha256'],
                    'size':     m['size'],
                    'mtime':    m['mtime'],
                    'launcher': m['launcher_root'],
                    'hack_term': m['hack'],
                },
            )
        # mc_info para banner del scan en panel
        self.mc_info = {
            'launcher': roots[0][0] if roots else None,
            'mods':     [m['name'] for m in mods_collected[:50]],
        }
        _print(f'  · {len(roots)} launcher root(s), {len(mods_collected)} mods sospechosos')

    # ── escaneo: browser history (compartido con Windows) ───────────────
    def scan_browser_history(self) -> None:
        _print('🌍 Historial de browsers...')
        tmpdir = tempfile.mkdtemp(prefix='argus_lin_hist_')
        try:
            for label, rel in BROWSER_HISTORY_PATHS:
                src = os.path.join(self.home, rel)
                if not os.path.exists(src):
                    continue
                copy = os.path.join(tmpdir, f'{label}.db')
                try:
                    shutil.copy2(src, copy)
                except OSError:
                    continue
                self._sniff_chromium_history(label, src, copy)

            for ff_root in FIREFOX_PROFILE_ROOTS:
                full = os.path.join(self.home, ff_root)
                if not os.path.isdir(full):
                    continue
                try:
                    for prof in os.listdir(full):
                        places = os.path.join(full, prof, 'places.sqlite')
                        if not os.path.isfile(places):
                            continue
                        copy = os.path.join(tmpdir, f'firefox_{prof[:8]}.db')
                        try:
                            shutil.copy2(places, copy)
                        except OSError:
                            continue
                        self._sniff_firefox_history(prof, places, copy)
                except OSError:
                    continue
        finally:
            shutil.rmtree(tmpdir, ignore_errors=True)

    def _sniff_chromium_history(self, label: str, src: str, db: str) -> None:
        try:
            conn = sqlite3.connect(f'file:{db}?mode=ro', uri=True, timeout=4)
            cur = conn.cursor()
            cur.execute('SELECT url, title FROM urls ORDER BY last_visit_time DESC LIMIT 1000')
            rows = cur.fetchall()
            conn.close()
        except sqlite3.Error:
            return
        matches = self._scan_history_rows(rows)
        if matches:
            self._add_issue(
                tipo='browser_history_cheat',
                nombre=f'{label}: {len(matches)} visita(s) a páginas de cheats',
                ruta=src,
                archivo=f'{label} History',
                categoria='NETWORK',
                alerta='CRITICAL',
                confidence=0.85,
                patterns=['browser_history', 'cheat_keyword', label.lower()],
                extra={'browser': label, 'match_count': len(matches), 'samples': matches[:5]},
            )

    def _sniff_firefox_history(self, prof: str, src: str, db: str) -> None:
        try:
            conn = sqlite3.connect(f'file:{db}?mode=ro', uri=True, timeout=4)
            cur = conn.cursor()
            cur.execute('SELECT url, title FROM moz_places ORDER BY last_visit_date DESC LIMIT 1000')
            rows = cur.fetchall()
            conn.close()
        except sqlite3.Error:
            return
        matches = self._scan_history_rows(rows)
        if matches:
            self._add_issue(
                tipo='browser_history_cheat',
                nombre=f'Firefox ({prof[:12]}): {len(matches)} visita(s) a páginas de cheats',
                ruta=src,
                archivo='Firefox places.sqlite',
                categoria='NETWORK',
                alerta='CRITICAL',
                confidence=0.85,
                patterns=['browser_history', 'cheat_keyword', 'firefox'],
                extra={'browser': 'Firefox', 'profile': prof, 'match_count': len(matches),
                       'samples': matches[:5]},
            )

    def _scan_history_rows(self, rows: list[tuple]) -> list[dict[str, Any]]:
        out = []
        for url, title in rows:
            haystack = (str(url or '') + ' ' + str(title or '')).lower()
            kw = None
            for d in CHEAT_DOMAINS:
                if d in haystack:
                    kw = d
                    break
            if not kw:
                hack = _smart_hack_match(haystack)
                if hack:
                    kw = hack
            if kw:
                out.append({'url': str(url or '')[:240], 'title': str(title or '')[:120], 'kw': kw})
        return out

    # ── escaneo: paquetes sospechosos instalados ────────────────────────
    def scan_installed_packages(self) -> None:
        _print('📦 Paquetes instalados (apt/dnf/pacman/flatpak)...')
        managers = []
        if _which('apt'):
            managers.append(('apt', ['apt', 'list', '--installed']))
        if _which('dpkg'):
            managers.append(('dpkg', ['dpkg', '-l']))
        if _which('rpm'):
            managers.append(('rpm', ['rpm', '-qa']))
        if _which('pacman'):
            managers.append(('pacman', ['pacman', '-Qq']))
        if _which('flatpak'):
            managers.append(('flatpak', ['flatpak', 'list', '--app', '--columns=application']))
        if _which('snap'):
            managers.append(('snap', ['snap', 'list']))

        for name, cmd in managers:
            rc, out, _err = _safe_run(cmd, timeout=20)
            if rc != 0:
                continue
            sus = []
            for ln in out.splitlines():
                ln_l = ln.lower()
                hack = _smart_hack_match(ln_l)
                if hack and not _is_legit_devtool(ln_l) and not _is_legit_mc_mod(ln_l):
                    sus.append({'pkg': ln.strip()[:160], 'hack': hack})
            if sus:
                self._add_issue(
                    tipo='installed_package_hack',
                    nombre=f'{name}: {len(sus)} paquete(s) instalados con hack-term',
                    ruta=f'{name} list',
                    archivo=name,
                    categoria='INSTALACION',
                    alerta='CRITICAL',
                    confidence=0.78,
                    patterns=['package_manager', name],
                    extra={'manager': name, 'count': len(sus), 'samples': sus[:10]},
                )

    # ── screenshot multi-display (Plataforma #9) ────────────────────────
    def take_screenshot(self) -> str | None:
        if not self.do_screenshot:
            return None
        _print('📸 Capturando screenshot...')
        # Intentar tools en orden de prioridad y compatibilidad
        out_path = os.path.join(tempfile.gettempdir(), f'argus_lin_{uuid.uuid4().hex[:8]}.png')

        is_wayland = bool(os.environ.get('WAYLAND_DISPLAY'))
        is_x11     = bool(os.environ.get('DISPLAY'))

        attempts: list[tuple[str, list[str]]] = []
        # Wayland first si aplica
        if is_wayland:
            if _which('grim'):
                attempts.append(('grim', ['grim', out_path]))  # wlroots: Hyprland/Sway
            if _which('gnome-screenshot'):
                attempts.append(('gnome-screenshot', ['gnome-screenshot', '-f', out_path]))
            if _which('spectacle'):
                attempts.append(('spectacle', ['spectacle', '-b', '-n', '-o', out_path]))
        if is_x11 or not is_wayland:
            if _which('scrot'):
                attempts.append(('scrot', ['scrot', '-z', out_path]))
            if _which('import'):
                attempts.append(('import', ['import', '-window', 'root', out_path]))
            if _which('maim'):
                attempts.append(('maim', ['maim', out_path]))

        for tool, cmd in attempts:
            rc, _o, err = _safe_run(cmd, timeout=8)
            if rc == 0 and os.path.exists(out_path) and os.path.getsize(out_path) > 0:
                _print(f'  · screenshot via {tool} ({os.path.getsize(out_path)//1024}KB)')
                # Comprimir base64 para upload
                try:
                    with open(out_path, 'rb') as f:
                        raw = f.read()
                    b64 = base64.b64encode(raw).decode('ascii')
                    return f'data:image/png;base64,{b64}'
                finally:
                    try: os.remove(out_path)
                    except OSError: pass
        _print('  · ⚠ No screenshot tool disponible (grim/scrot/import/gnome-screenshot/spectacle/maim)')
        return None

    # ── upload al backend ───────────────────────────────────────────────
    def upload_start(self) -> bool:
        if self.offline:
            return True
        _print(f'⬆  Iniciando scan en {self.server}...')
        try:
            country = _detect_country()
        except Exception:
            country = ''
        body = {
            'token':              self.token,
            'machine_id':         _machine_id(),
            'machine_name':       self.machine_name,
            'country':            country,
            'minecraft_username': self.mc_username,
            'os':                 _os_label(),
            'mc_version':         self.mc_info.get('version'),
            'mc_launcher':        self.mc_info.get('launcher'),
            'mc_mods':            self.mc_info.get('mods', []),
        }
        try:
            resp = _http_post_json(f'{self.server}/api/scans', body, timeout=20)
        except Exception as e:
            _print(f'  · ❌ {e}')
            return False
        if resp.get('error'):
            _print(f'  · ❌ {resp["error"]}')
            return False
        self.scan_id = int(resp.get('scan_id', 0))
        _print(f'  · scan_id={self.scan_id}')
        return self.scan_id > 0

    def upload_results(self, screenshot_b64: str | None) -> bool:
        if self.offline:
            return True
        if not self.scan_id:
            return False
        _print(f'⬆  Subiendo resultados al scan {self.scan_id}...')
        body = {
            'status':              'completed',
            'total_files_scanned': self.total_files,
            'total_dirs_scanned':  self.total_dirs,
            'issues_found':        len(self.issues),
            'scan_duration':       int(time.time() - self.t_start),
            'results':             self.issues,
            'screenshot':          screenshot_b64,
            'mc_version':          self.mc_info.get('version'),
            'mc_launcher':         self.mc_info.get('launcher'),
            'mc_mods':             self.mc_info.get('mods', []),
        }
        try:
            resp = _http_post_json(f'{self.server}/api/scans/{self.scan_id}/results',
                                    body, timeout=60)
        except Exception as e:
            _print(f'  · ❌ {e}')
            return False
        if resp.get('error'):
            _print(f'  · ❌ {resp["error"]}')
            return False
        _print(f'  · ✓ {len(self.issues)} issue(s) subidas')
        return True

    # ── runner principal ────────────────────────────────────────────────
    def run(self) -> int:
        _print(f'🦅 ArgusScanner Linux v{SCANNER_VERSION}')
        _print(f'   user={self.mc_username} machine={self.machine_name}')
        _print(f'   home={self.home} root={"yes" if _is_root() else "no"}')
        _print('')

        if not self.upload_start():
            _print('⚠ No se pudo iniciar el scan en el servidor (continuando offline-only).')
            self.offline = True

        scans = (
            self.scan_minecraft_launchers,
            self.scan_xdg_trash,
            self.scan_shell_history,
            self.scan_journalctl_java,
            self.scan_proc_processes,
            self.scan_open_windows,
            self.scan_browser_history,
            self.scan_installed_packages,
        )
        for fn in scans:
            try:
                fn()
            except Exception as e:
                _print(f'  ⚠ {fn.__name__}: {type(e).__name__}: {e}')

        screenshot = self.take_screenshot()

        if not self.offline:
            if not self.upload_results(screenshot):
                _print('⚠ Upload de resultados falló — guardando localmente.')
                self._save_local_report()
        else:
            self._save_local_report()

        elapsed = int(time.time() - self.t_start)
        _print('')
        _print(f'✅ Scan completo: {len(self.issues)} issue(s) en {elapsed}s')
        if not self.offline and self.scan_id:
            _print(f'   Ver: {self.server}/panel#scan={self.scan_id}')
        return 0

    def _save_local_report(self) -> None:
        out_path = os.path.join(
            tempfile.gettempdir(),
            f'argus_lin_report_{int(time.time())}.json',
        )
        try:
            with open(out_path, 'w', encoding='utf-8') as f:
                json.dump({
                    'scanner_version': SCANNER_VERSION,
                    'machine_name': self.machine_name,
                    'mc_username':  self.mc_username,
                    'os':           _os_label(),
                    'duration_s':   int(time.time() - self.t_start),
                    'issues':       self.issues,
                    'mc_info':      self.mc_info,
                }, f, indent=2, ensure_ascii=False)
            _print(f'📄 Reporte local: {out_path}')
        except OSError as e:
            _print(f'❌ No se pudo guardar reporte: {e}')


# ─────────────────────────── helpers globales ───────────────────────────────
def urllib_unquote(s: str) -> str:
    try:
        from urllib.parse import unquote
        return unquote(s)
    except Exception:
        return s


def _sha256_file(path: str, chunk: int = 65536) -> str:
    try:
        h = hashlib.sha256()
        with open(path, 'rb') as f:
            while True:
                data = f.read(chunk)
                if not data:
                    break
                h.update(data)
        return h.hexdigest()
    except OSError:
        return ''


def _machine_id() -> str:
    """Identificador estable del host."""
    candidates = ('/etc/machine-id', '/var/lib/dbus/machine-id')
    for p in candidates:
        if os.path.exists(p):
            try:
                with open(p, 'r') as f:
                    return f.read().strip()[:64]
            except OSError:
                continue
    # Fallback: hostname + uid
    return hashlib.sha1((socket.gethostname() + str(os.getuid())).encode()).hexdigest()[:32]


def _os_label() -> str:
    """e.g. 'Linux Ubuntu 24.04' / 'Linux Arch' — máx 32 chars."""
    distro = ''
    try:
        if os.path.exists('/etc/os-release'):
            with open('/etc/os-release') as f:
                for ln in f:
                    if ln.startswith('PRETTY_NAME='):
                        distro = ln.split('=', 1)[1].strip().strip('"')
                        break
    except OSError:
        pass
    if not distro:
        try:
            distro = platform.platform(terse=True)
        except Exception:
            distro = 'Linux'
    return f'Linux {distro}'[:32]


def _detect_country() -> str:
    """Best-effort: GeoIP via ipinfo.io fallback. Si no hay net, vacío."""
    try:
        with urllib.request.urlopen('https://ipinfo.io/country', timeout=4) as resp:
            return resp.read().decode('ascii').strip()[:8]
    except Exception:
        return ''


def _http_post_json(url: str, body: dict[str, Any], timeout: int = 20) -> dict[str, Any]:
    data = json.dumps(body).encode('utf-8')
    req = urllib.request.Request(
        url, data=data, method='POST',
        headers={'Content-Type': 'application/json',
                 'User-Agent': f'ArgusScannerLinux/{SCANNER_VERSION}'},
    )
    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            txt = resp.read().decode('utf-8', errors='ignore')
            try:
                return json.loads(txt)
            except json.JSONDecodeError:
                return {'_raw': txt, '_status': resp.status}
    except urllib.error.HTTPError as e:
        try:
            err_txt = e.read().decode('utf-8', errors='ignore')
            return json.loads(err_txt)
        except Exception:
            return {'error': f'HTTP {e.code}'}


# ─────────────────────────── CLI ────────────────────────────────────────────
def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        prog='argus-linux',
        description='ArgusScanner para Linux — verificación anti-cheat de Minecraft Java.',
    )
    parser.add_argument('--token', '-t', required=True,
                        help='Token de scan generado por el staff (panel.argus)')
    parser.add_argument('--server', '-s', default=DEFAULT_SERVER,
                        help=f'URL del backend (default: {DEFAULT_SERVER})')
    parser.add_argument('--no-screenshot', action='store_true',
                        help='No capturar screenshot (útil en headless / VPS)')
    parser.add_argument('--offline', action='store_true',
                        help='No subir al backend, solo generar reporte JSON local')
    parser.add_argument('--machine-name', default=None,
                        help='Nombre de la máquina (default: hostname)')
    parser.add_argument('--mc-username', default=None,
                        help='Username de Minecraft del jugador (default: $USER)')
    parser.add_argument('--scan-self', action='store_true',
                        help='Smoke test: corre todas las scans en modo offline y sale')
    args = parser.parse_args(argv)

    if args.scan_self:
        args.offline = True
        args.no_screenshot = True

    scanner = LinuxScanner(
        token=args.token,
        server=args.server,
        do_screenshot=not args.no_screenshot,
        offline=args.offline,
        machine_name=args.machine_name,
        mc_username=args.mc_username,
    )
    return scanner.run()


if __name__ == '__main__':
    sys.exit(main())
