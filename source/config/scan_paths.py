"""
Rutas críticas, extensiones y pruning inteligente para el escaneo de archivos.
Objetivo: más profundidad donde importa (mods, launchers, temp) sin perder FPS.
"""
from __future__ import annotations

import os
from typing import Iterable, List, Sequence, Tuple

# ── Extensiones relevantes (lookup O(1)) ─────────────────────────────────────
RELEVANT_EXTENSIONS: frozenset[str] = frozenset({
    '.jar', '.exe', '.dll', '.bat', '.cmd', '.ps1', '.vbs', '.js', '.py',
    '.class', '.java', '.lua', '.txt', '.log', '.cfg', '.config', '.json',
    '.properties', '.yml', '.yaml', '.xml', '.dat', '.bin', '.cache',
    '.tmp', '.temp', '.bak', '.backup', '.old', '.new', '.mod', '.minecraft',
    '.zip', '.rar', '.7z', '.tar', '.gz', '.msi', '.msm', '.msp', '.litemod',
    '.disabled', '.input', '.ahk',
})

# Nombres de carpeta: no descender (match exacto case-insensitive)
SKIP_DIR_NAMES: frozenset[str] = frozenset({
    'node_modules', '.git', '__pycache__', 'venv', '.venv', '.idea', '.vscode',
    'winsxs', 'servicing', 'driverstore', 'systemresources', 'panther',
    'packages',  # Windows Store bulk — salvo paths explícitos en critical
    '$recycle.bin', 'system volume information', 'recovery',
    'google', 'chrome', 'firefox', 'edge', 'brave-browser', 'vivaldi', 'opera',
    'user data', 'default', 'profiles', 'cache', 'temp', 'tmp', 'code cache', 'gpuarchives',
    'shadercache', 'grshadercache', 'browsermetrics',
    'assets', 'libraries', 'versions', 'logs', 'crash-reports', 'screenshots',
    'saves', 'resourcepacks', 'shaderpacks', 'backups', 'runtime', 'natives',
    'webcache', 'inetcache', 'history', 'cookies',
})

# Dentro de .minecraft / launchers: omitir vanilla pesado pero NO mods/config
MC_VANILLA_DIR_NAMES: frozenset[str] = frozenset({
    'assets', 'libraries', 'versions', 'logs', 'crash-reports', 'screenshots',
    'saves', 'backups', 'runtime', 'natives', 'webcache',
})

# Fragmentos de ruta: no descender (navegadores, juegos ruidosos)
SKIP_PATH_FRAGMENTS: Tuple[str, ...] = (
    'google\\chrome', 'mozilla\\firefox', 'microsoft\\edge',
    'brave-browser', 'vivaldi', 'opera software',
    'appdata\\local\\google', 'appdata\\roaming\\mozilla',
    'appdata\\local\\osu!', 'appdata\\roaming\\osu!',
    'appdata\\locallow\\hyperbolic magnetism',
    'appdata\\locallow\\robtop games',
    '\\.git\\', '\\node_modules\\',
    'steam\\steamapps\\common\\garrysmod\\garrysmod\\addons',
    'appdata\\roaming\\image-line', 'appdata\\local\\spotify',
    'windows\\winsxs', 'windows\\system32', 'windows\\syswow64',
    'windows\\softwaredistribution\\download',
)

# Profundidad máxima por tipo de raíz
DEPTH_DEFAULT = 5
DEPTH_MC_ROOT = 8
DEPTH_SHALLOW = 4


def filter_relevant_files(files: Iterable[str]) -> List[str]:
    out: List[str] = []
    for f in files:
        ext = os.path.splitext(f)[1].lower()
        if ext in RELEVANT_EXTENSIONS:
            out.append(f)
    return out


def _norm_path(p: str) -> str:
    return p.lower().replace('/', '\\')


def _in_minecraft_tree(root_lower: str) -> bool:
    markers = (
        '.minecraft\\', '.minecraft/',
        '\\instances\\', '/instances/',
        'curseforge\\minecraft', 'modrinth',
        'prismlauncher', 'multimc', 'gdlauncher', 'atlauncher', 'ftbapp',
        'polymc', 'sklauncher', 'tlauncher', 'labymod',
    )
    return any(m in root_lower for m in markers)


def should_skip_dir(root: str, dirname: str) -> bool:
    """True si no debemos descender a dirname desde root."""
    name = (dirname or '').lower()
    root_lower = _norm_path(root)

    if name in SKIP_DIR_NAMES:
        # cache/temp del sistema sí escaneamos si estamos en ruta de usuario explícita
        if name in ('cache', 'temp', 'tmp') and any(
            frag in root_lower for frag in (
                '\\downloads\\', '\\desktop\\', '\\documents\\',
                '\\appdata\\local\\temp', '\\windows\\temp',
                '.minecraft\\', '\\instances\\', 'curseforge',
            )
        ):
            return False
        if name in ('cache', 'temp', 'tmp'):
            return True
        return True

    if _in_minecraft_tree(root_lower) and name in MC_VANILLA_DIR_NAMES:
        return True

    if any(frag in root_lower for frag in SKIP_PATH_FRAGMENTS):
        return True

    # Subcarpetas de navegador por nombre
    if name in ('application data', 'local storage', 'session storage', 'indexeddb'):
        return True

    return False


def prune_walk_dirs(root: str, dirs: List[str]) -> None:
    """Mutación in-place de dirs para os.walk (dirs[:] = ...)."""
    kept = []
    for d in dirs:
        if not should_skip_dir(root, d):
            kept.append(d)
    dirs[:] = kept


def max_depth_for_root(critical_path: str) -> int:
    p = _norm_path(critical_path)
    if '.minecraft' in p or 'instances' in p or 'curseforge' in p or 'modrinth' in p:
        return DEPTH_MC_ROOT
    if any(x in p for x in ('downloads', 'desktop', 'documents', 'temp', 'prefetch')):
        return DEPTH_DEFAULT
    return DEPTH_SHALLOW


def depth_at_root(root: str, critical_path: str) -> int:
    try:
        root_n = os.path.normcase(os.path.abspath(root))
        base_n = os.path.normcase(os.path.abspath(critical_path))
        if not root_n.startswith(base_n):
            return 0
        rel = root_n[len(base_n):].strip('\\/')
        if not rel:
            return 0
        return rel.count('\\') + rel.count('/')
    except Exception:
        return root.count(os.sep) - critical_path.count(os.sep)


def get_critical_paths(user_home: str, drive: str) -> List[str]:
    """Rutas de alto valor para hacks MC — ordenadas por prioridad."""
    uh = user_home or os.path.expanduser('~')
    local = os.path.join(uh, 'AppData', 'Local')
    roam = os.path.join(uh, 'AppData', 'Roaming')

    paths = [
        os.path.join(roam, '.minecraft'),
        os.path.join(roam, '.vape'),
        os.path.join(roam, 'lunarclient'),
        os.path.join(roam, 'lunar-launcher'),
        os.path.join(roam, 'feather'),
        os.path.join(roam, '.feather'),
        os.path.join(roam, 'PrismLauncher'),
        os.path.join(roam, 'gdlauncher'),
        os.path.join(roam, 'MultiMC'),
        os.path.join(roam, 'ATLauncher'),
        os.path.join(roam, 'cosmic'),
        os.path.join(roam, 'Badlion Client'),
        os.path.join(roam, 'Polymc'),
        os.path.join(roam, 'PolyMC'),
        os.path.join(roam, '.tlauncher'),
        os.path.join(roam, 'sklauncher'),
        os.path.join(roam, 'com.modrinth'),
        os.path.join(roam, '.labymod'),
        os.path.join(roam, 'labymod-neo'),
        os.path.join(local, 'Overwolf'),
        os.path.join(local, 'Programs'),
        os.path.join(local, 'ftblauncher'),
        os.path.join(local, 'ModrinthApp'),
        os.path.join(local, 'Packages'),
        os.path.join(local, 'Temp'),
        os.path.join(uh, 'Downloads'),
        os.path.join(uh, 'Desktop'),
        os.path.join(uh, 'Documents'),
        os.path.join(uh, 'OneDrive'),
        os.path.join(drive, 'Windows', 'Temp'),
        os.path.join(drive, 'Windows', 'Prefetch'),
        os.path.join(local, 'MicrosoftEdgeDownloads'),
    ]

    # CurseForge / FTB en varias ubicaciones
    for base in (local, roam):
        for sub in (
            'curseforge', 'CurseForge', 'FTB App', 'ftb-app',
            'com.curseforge', '.curseforge',
        ):
            paths.append(os.path.join(base, sub))

    # Otros usuarios en el equipo
    users_dir = os.path.join(drive, 'Users')
    if os.path.isdir(users_dir):
        try:
            for user_folder in os.listdir(users_dir):
                if user_folder in ('Default', 'Public', 'All Users', 'Default User'):
                    continue
                up = os.path.join(users_dir, user_folder)
                if not os.path.isdir(up):
                    continue
                for rel in (
                    r'AppData\Roaming\.minecraft',
                    r'AppData\Roaming\PrismLauncher',
                    r'AppData\Roaming\MultiMC',
                    r'AppData\Roaming\gdlauncher',
                    r'AppData\Roaming\lunarclient',
                    r'AppData\Roaming\feather',
                    r'AppData\Local\Temp',
                    r'Downloads',
                    r'Desktop',
                ):
                    paths.append(os.path.join(up, *rel.split('\\')))
        except OSError:
            pass

    seen = set()
    out: List[str] = []
    for p in paths:
        pn = os.path.normcase(os.path.abspath(p))
        if pn not in seen and os.path.exists(p):
            seen.add(pn)
            out.append(p)
    return out


def scan_timeout_seconds(cpu_count: int | None = None) -> int:
    """Timeout por unidad — un poco más generoso si hay cores (pruning libera I/O)."""
    n = cpu_count or 4
    if n < 4:
        return 85
    if n < 8:
        return 75
    return 68
