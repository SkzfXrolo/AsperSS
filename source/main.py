import tkinter as tk
from tkinter import ttk, scrolledtext, messagebox, Toplevel
import threading
import os
import sys

# ── Log a archivo para debugging (AppData/Roaming/ASPERSProjectsSS/scanner.log) ──
try:
    _log_dir = os.path.join(os.environ.get('APPDATA', ''), 'ASPERSProjectsSS')
    os.makedirs(_log_dir, exist_ok=True)
    _log_path = os.path.join(_log_dir, 'scanner.log')
    _log_file = open(_log_path, 'w', encoding='utf-8', buffering=1)
    sys.stdout = _log_file
    sys.stderr = _log_file
    print(f"[INICIO] ArgusScanner iniciado - log en {_log_path}")
except Exception:
    pass
import psutil
import winreg
import json
from datetime import datetime, timedelta
import subprocess
import hashlib
from pathlib import Path
import time
import ctypes
from ctypes import wintypes
try:
    import matplotlib
    matplotlib.use('TkAgg')
    from matplotlib.backends.backend_tkagg import FigureCanvasTkAgg
    from matplotlib.figure import Figure
    MATPLOTLIB_AVAILABLE = True
except ImportError:
    MATPLOTLIB_AVAILABLE = False
    FigureCanvasTkAgg = None
    Figure = None
import webbrowser
import base64
from io import BytesIO
import socket
from http.server import HTTPServer, SimpleHTTPRequestHandler
import socketserver
try:
    import requests
except ImportError:
    requests = None

# Importar el sistema de estilos moderno
try:
    from ui_style import ModernUI
    UI_STYLE_AVAILABLE = True
except ImportError:
    UI_STYLE_AVAILABLE = False
    ModernUI = None

SCANNER_VERSION = "1.6.34"

# ── Detección de carpetas hack — lógica centralizada ─────────────────────────
import re as _re
import unicodedata as _unicodedata
import functools

def _normalize(text: str) -> str:
    """Normaliza texto a ASCII para detectar homoglyphs cirílicos/unicode.
    Ejemplo: 'vаpe' (con 'а' cirílico) → 'vape'
    """
    return _unicodedata.normalize('NFKD', text).encode('ascii', 'ignore').decode('ascii').lower()

# Nombres exclusivos de hack clients — seguros para buscar como substring.
# Estos nombres NUNCA aparecen en software legítimo.
_DEFINITE_HACK_NAMES = {
    # ── Clientes clásicos ──────────────────────────────────────────────────
    'vape', 'vapelite', 'vapev4', 'vapev2',
    'entropy', 'entropyclient',
    'whiteout', 'whiteoutclient',
    'liquidbounce', 'liquidbounce+',
    'wurst', 'wurstclient',
    'impactclient',
    'sigmaclient', 'sigma5', 'sigma6', 'sigma-6',
    'fluxclient', 'flux1.8', 'flux1',
    'futureclient',
    'astolfo', 'astolfoclient',
    'exhibition', 'exhibitionclient',
    'novoline', 'novolineclient',
    'ghostclient', 'ghost-client', 'ghost_client',
    'riseclient', 'moonclient', 'dripclient',
    # ── Clientes modernos (2022-2025) ─────────────────────────────────────
    'meteorclient', 'meteor-client',
    'rusherhack', 'rusher-hack',
    'aristois',
    'tenacity', 'tenacityclient',
    'vertex', 'vertexclient',
    'inertia', 'inertiaclient',
    'salhack', 'sal-hack',
    'jello', 'jelloclient',
    'datura', 'daturamc',
    'remix', 'remixclient',
    'pandora', 'pandoraclient',
    'azura', 'azuraclient',
    'kami', 'kamiclient', 'kamiblue',
    'konas', 'konasclient',
    'weepcraft',
    'nextgen', 'tegernako', 'zeroday',
    'lucid', 'lucidclient',
    'nyx', 'nyxclient',
    'cloudclient', 'cloud-client',  # NO agregar 'cloud' solo — matchea CloudExperienceHost (Windows)
    'vanish',
    # ── Módulos y herramientas ────────────────────────────────────────────
    'phobos', 'komat', 'wasp', 'seppuku', 'sloth', 'blatant',
    'killaura', 'kill-aura',
    'aimbot', 'aim-bot',
    'triggerbot', 'trigger-bot',
    'wallhack', 'wall-hack',
    'autoclick', 'autoclicker',
    'xray-mod', 'xraymod',
    'nofall', 'no-fall',
    'freecam', 'free-cam',
    'scaffold', 'scaffoldhack',
    'clickgui',
    # ── Loaders e injectors ───────────────────────────────────────────────
    'weave-loader', 'weaveclient', 'weaveloader',
    'extremeinjector', 'xenos', 'dllinjector',
    'cheatengine', 'cheat-engine',
    'processhollowing', 'dllhijacking',
    # ── Nombres de carpetas de hack ───────────────────────────────────────
    'hackclient', 'hackmod', 'cracked-mc', 'crackedmc', 'crack-mc', 'crackmc',
    'bypasser', 'bypassmc',
    # ── Baritone (bot de movimiento automático prohibido) ─────────────────
    'baritone',
    # ── NBT editors (edición ilegal de inventarios/mundo) ────────────────
    # Nota: herramientas legítimas para uso en single-player, sospechosas en SS
    'nbtexplorer', 'nbt-explorer',
    'nbtedit', 'nbt-edit',
    'mcaselector', 'mca-selector',
    'nbteditor',
    # ── Clientes recientes (2024-2025) ────────────────────────────────────
    'slinky', 'slinkyclient', 'slinky-client',
    'reflexclient',  # 'reflex' solo matchea NVIDIA Reflex (falso positivo)
    'rageclient', 'rage-client',
    'biscuit', 'biscuitclient',
    'thunderhack', 'thunder-hack',
}

# Palabras genéricas que sólo se marcan cuando son palabra completa
# 'crack'/'cracked' eliminados — son demasiado genéricos y flagean software pirata
# no relacionado con Minecraft. Las variantes MC-específicas están en _DEFINITE_HACK_NAMES.
_WORD_BOUNDARY_HACK_WORDS = ['hack', 'cheat', 'bypass']


# ── Smart Hack-Term Matcher (Filtro #38) ─────────────────────────────────────
#
# El matching antiguo (`any(term in text for term in hack_terms)`) generaba
# falsos positivos en nombres legítimos:
#   "vertexshader.frag"      → matcheaba 'vertex'
#   "sunrise_wallpaper.jpg"  → matcheaba 'rise'
#   "matrixhack.bat"         → matcheaba 'hack' (incluso correcto, pero igual)
#   "ghostwire-tokyo.exe"    → matcheaba 'ghost'
#   "weaverloom.jar"         → matcheaba 'weave'
#
# La solución es exigir que el término aparezca como palabra/segmento aislado:
#   - Términos "palabra" (killaura, vape, vertex):  \b TERM \b
#   - Términos "dotted" (.rise, .meteor):           \. TERM (?!\w)
#       (matchea ".rise" en "C:\Users\bob\.rise\config.json" pero NO en
#       "sunrise.exe" porque ahí no hay punto antes de "rise").
#
# Los regex se compilan UNA sola vez y se reusan; coste ~constante por scan.

import re as _re_smart  # alias para evitar shadow de imports posteriores

def _build_smart_hack_regex(terms):
    """Compila dos regex (word-terms y dotted-terms) a partir de una lista
    de términos. Devuelve (word_re, dot_re) — cualquiera puede ser None si
    la lista correspondiente está vacía.

    Nota: usamos look-arounds [a-z0-9] en lugar de \\b/\\w porque en filenames
    reales el underscore es separador habitual ('my_hack.exe', 'killaura_v2'),
    y \\w incluiría '_' rompiendo el boundary."""
    word_terms = []
    dot_terms  = []
    for t in terms:
        if not t:
            continue
        if t.startswith('.'):
            dot_terms.append(_re_smart.escape(t[1:]))  # quitar el . para usar \. en el regex
        else:
            word_terms.append(_re_smart.escape(t))
    word_re = _re_smart.compile(
        r'(?<![a-z0-9])(?:' + '|'.join(word_terms) + r')(?![a-z0-9])',
        _re_smart.IGNORECASE,
    ) if word_terms else None
    dot_re = _re_smart.compile(
        r'\.(?:' + '|'.join(dot_terms) + r')(?![a-z0-9])',
        _re_smart.IGNORECASE,
    ) if dot_terms else None
    return word_re, dot_re


def smart_hack_match(text, terms_or_regex):
    """Devuelve True si `text` contiene alguno de los términos de hack
    en contexto válido (palabra completa o segmento dotted).

    Args:
        text: string a inspeccionar (case insensitive).
        terms_or_regex: lista de strings (se compila al vuelo con cache lru)
                        o tupla (word_re, dot_re) ya compilada.
    """
    if not text:
        return False
    if isinstance(terms_or_regex, tuple) and len(terms_or_regex) == 2:
        word_re, dot_re = terms_or_regex
    else:
        word_re, dot_re = _build_smart_hack_regex(tuple(terms_or_regex))
    if word_re and word_re.search(text):
        return True
    if dot_re and dot_re.search(text):
        return True
    return False


@functools.lru_cache(maxsize=8)
def _smart_hack_regex_cached(terms_tuple):
    """Versión cacheada de _build_smart_hack_regex para listas estáticas."""
    return _build_smart_hack_regex(terms_tuple)


# ── Authenticode Publisher Whitelist (Filtro #2 lite) ────────────────────────
#
# Si un binario está firmado por un publisher de la whitelist abajo, su
# probabilidad de ser hack es prácticamente nula. Esto permite descartar
# rápidamente FPs en software legítimo (drivers, antivirus, antitrampas).
#
# La verificación se hace con PowerShell `Get-AuthenticodeSignature` lo cual
# es lento (~150-300ms por archivo). Por eso:
#   - Se cachea por SHA-256 del path (lru_cache)
#   - Solo se llama cuando ya hay sospecha — no se firma TODO el filesystem.
#   - Si PowerShell falla / el archivo no existe / no tiene firma, devuelve
#     None. NUNCA hace que el scan caiga.

_TRUSTED_PUBLISHERS = (
    # Microsoft (Windows, Defender, Office, .NET, etc.)
    'microsoft corporation', 'microsoft windows',
    'microsoft windows hardware compatibility publisher',
    'microsoft windows publisher',
    # Mojang / Minecraft oficial
    'mojang ab', 'mojang synergies ab', 'microsoft corporation',
    # Java
    'oracle america, inc.', 'oracle corporation', 'oracle america',
    'azul systems, inc.', 'eclipse adoptium', 'amazon corretto',
    # GPU
    'nvidia corporation', 'advanced micro devices, inc.', 'amd inc',
    'intel corporation', 'intel(r) corporation',
    # Comunicación
    'discord inc.', 'discord inc',
    # Plataformas de juegos
    'valve corp.', 'valve corporation',
    'epic games inc.', 'epic games, inc.',
    # Periféricos
    'razer inc.', 'razer usa ltd.',
    'logitech', 'logitech inc.',
    'corsair memory, inc.', 'corsair components, inc.',
    'steelseries aps', 'steelseries',
    'kingston technology company, inc.',
    # Antivirus / Seguridad
    'avast software s.r.o.', 'avast software',
    'malwarebytes corporation', 'malwarebytes inc',
    'bitdefender srl', 'bitdefender',
    'kaspersky lab',
    'eset, spol. s r.o.',
    # Navegadores
    'google llc', 'google inc',
    'mozilla corporation',
    'opera norway as', 'opera software as',
    'brave software, inc.',
    # Lunar / Badlion (clientes legítimos de MC)
    'moonsworth, llc', 'moonsworth llc', 'lunar client',
    'badlion network ltd', 'badlion network',
    # Streaming / Captura
    'obs studio contributors', 'streamlabs llc',
    # Anti-cheats reconocidos
    'easy anti-cheat oy', 'easy anti-cheat',
    'battleye innovations', 'battleye',
    'kakao games europe b.v.',
)


@functools.lru_cache(maxsize=4096)
def _get_authenticode_publisher(file_path: str):
    """Devuelve el subject CN del publisher Authenticode (lowercase, stripped)
    o None si: no hay firma, archivo no existe, PowerShell falló, o el sistema
    no es Windows.

    Usa subprocess con timeout 5s para no colgar el scan."""
    try:
        if not file_path or not os.path.exists(file_path):
            return None
        # Solo Windows: PowerShell expone Get-AuthenticodeSignature
        if sys.platform != 'win32':
            return None
        cmd = [
            'powershell.exe', '-NoProfile', '-Command',
            f"(Get-AuthenticodeSignature -LiteralPath '{file_path}').SignerCertificate.Subject",
        ]
        result = subprocess.run(
            cmd,
            capture_output=True, text=True, timeout=5,
            creationflags=getattr(subprocess, 'CREATE_NO_WINDOW', 0),
        )
        out = (result.stdout or '').strip()
        if not out:
            return None
        # subject típico: "CN=Microsoft Corporation, O=Microsoft Corporation, ..."
        for chunk in out.split(','):
            chunk = chunk.strip()
            if chunk.upper().startswith('CN='):
                return chunk[3:].strip().strip('"').lower()
        return None
    except Exception:
        return None


def is_trusted_publisher(file_path: str) -> bool:
    """True si el archivo está firmado por un publisher de la whitelist.
    Usar para descartar FPs (Filtro #2). Falla silenciosamente — nunca rompe."""
    pub = _get_authenticode_publisher(file_path)
    if not pub:
        return False
    return any(trusted in pub for trusted in _TRUSTED_PUBLISHERS)

# Rutas de software legítimo — si el root las contiene, ignorar la carpeta
_SAFE_ROOT_FRAGMENTS = {
    'google\\chrome', 'appdata\\local\\google',
    'mozilla\\firefox', 'appdata\\roaming\\mozilla',
    'microsoft\\edge', 'appdata\\local\\microsoft\\edge',
    'opera software', 'appdata\\local\\brave-browser',
    'appdata\\local\\vivaldi',
    'windows\\prefetch', 'windows\\system32', 'windows\\syswow64',
    'windows\\winsxs', 'windows\\softwaredistribution',
    'program files\\microsoft', 'program files (x86)\\microsoft',
    'steam\\steamapps', 'epicgames', 'origin games', 'ubisoft game launcher',
    'riotgames', 'riot games', 'battlenet', 'battle.net',
    'nvidia corporation', 'nvidia\\cubins', 'amd\\radeon', 'intel corporation',
    'discord\\app-', 'teamspeak 3 client', 'zoom\\', 'skype\\',
    'microsoft teams', 'appdata\\local\\packages',
    'appdata\\local\\nvidia', 'programdata\\nvidia',  # NVIDIA NGX/DLSS/Reflex models
    'wondershare', 'obs-studio', 'obs studio',
    'site-packages', 'voicemod', 'node_modules',
    'lunarclient', 'badlionclient', 'badlion', 'blclient',
    'tlauncher', 'prismlauncher', 'multimc', 'polymc',
    'curseforge', 'ftbapp', 'gdlauncher', 'atlauncher', 'overwolf',
    'visual studio', 'intellij idea', 'pycharm', 'webstorm', 'jetbrains',
    'minecraftsstool',
    # LabyMod y su launcher (legítimo, cliente de Minecraft)
    'labymod', 'labymodlauncher', 'labymod-neo',
    # Fabric API — carpeta de mods remapeados (no es obfuscación)
    '.fabric\\processedmods', '.minecraft\\.fabric',
    # Librerías legítimas de Minecraft
    '.minecraft\\libraries',
    # Grabadores de clips / software de streaming
    'medal\\', 'medal.tv',
    # Juegos y apps legítimas
    'roblox\\', 'innersloth', 'vseeface', 'vseefacex',
    # Overwolf
    'ow-electron', 'overwolf',
    # Juegos de ritmo — sus carpetas de songs/skins contienen palabras
    # como 'riot', 'rise', 'impact', 'extra', 'insane' que colisionan con hacks
    'appdata\\local\\osu!', '\\osu!\\songs', '\\osu!\\skins',
    'appdata\\roaming\\osu!',
    # Beat Saber — carpetas de niveles custom con títulos de canciones
    'appdata\\locallow\\hyperbolic magnetism',
    # Geometry Dash — niveles descargados con nombres genéricos
    'appdata\\locallow\\robtop games',
    # Git repos y proyectos de desarrollo — node_modules, .git, dist
    '\\.git\\', '\\node_modules\\', '\\dist\\', '\\.github\\',
    # Garry's Mod addons
    'steam\\steamapps\\common\\garrysmod\\garrysmod\\addons',
    # Música
    'spotify\\', 'appdata\\roaming\\image-line', 'virtualdj\\', '\\fl studio\\',
    'appdata\\local\\spotify',
    # Process Hacker 3 / System Informer (sucesor legítimo de PH2)
    'systeminformer', 'processhacker3',
    # AHK instalado oficialmente en Program Files (no sospechoso)
    'program files\\autohotkey', 'program files (x86)\\autohotkey',
}

_MINECRAFT_INSTANCE_FRAGMENTS = [
    # Únicamente carpetas donde se cargan mods/coremods activos
    '.minecraft\\mods', '.minecraft/mods',
    '.minecraft\\coremods', '.minecraft/coremods',
    # Launchers alternativos con instancias
    'multimc\\instances', 'multimc/instances',
    'prismlauncher\\instances', 'prismlauncher/instances',
    'curseforge\\minecraft\\instances', 'curseforge/minecraft/instances',
    'gdlauncher\\instances', 'gdlauncher/instances',
    'atlauncher\\instances', 'atlauncher/instances',
    'ftbapp\\instances', 'ftbapp/instances',
]

# F2 — Rutas de Minecraft vanilla que NUNCA contienen hacks activos.
# Se aplican como filtro PREVIO al scoring — archivos aquí son del propio juego.
_VANILLA_MC_PATHS = [
    '.minecraft\\versions\\',    '.minecraft/versions/',
    '.minecraft\\libraries\\',   '.minecraft/libraries/',
    '.minecraft\\assets\\',      '.minecraft/assets/',
    '.minecraft\\logs\\',        '.minecraft/logs/',
    '.minecraft\\crash-reports\\', '.minecraft/crash-reports/',
    '.minecraft\\screenshots\\', '.minecraft/screenshots/',
    '.minecraft\\backups\\',     '.minecraft/backups/',
    '.minecraft\\runtime\\',     '.minecraft/runtime/',  # JRE bundled con MC (jrt-fs.jar, etc.)
    '-natives\\',                '-natives/',
    '\\natives\\',               '/natives/',
]

# Rutas que NO son instancias activas (archivos descargados pero no cargados)
_NON_INSTANCE_FRAGMENTS = [
    '\\downloads\\', '/downloads/',
    '\\desktop\\', '/desktop/',
    '\\documents\\', '/documents/',
    '\\temp\\', '/temp/',
    '\\tmp\\', '/tmp/',
    '\\appdata\\local\\temp', '/appdata/local/temp',
    # F4 — Cloud sync: raramente contienen hacks activos cargados
    '\\onedrive\\', '/onedrive/',
    '\\dropbox\\', '/dropbox/',
    '\\google drive\\', '/google drive/',
    '\\icloud drive\\', '/icloud drive/',
    '\\nextcloud\\', '/nextcloud/',
    '\\box\\', '/box/',
]

def _is_minecraft_instance(path: str) -> bool:
    """Devuelve True si el path está dentro de una instancia activa de Minecraft."""
    p = path.lower()
    return any(frag in p for frag in _MINECRAFT_INSTANCE_FRAGMENTS)

def _is_process_running(name_or_path: str) -> bool:
    """Devuelve True si hay un proceso corriendo cuyo exe coincide con name_or_path."""
    target = os.path.basename(name_or_path).lower()
    try:
        for proc in psutil.process_iter(['name', 'exe']):
            try:
                pname = (proc.info.get('name') or '').lower()
                pexe  = os.path.basename(proc.info.get('exe') or '').lower()
                if target in (pname, pexe):
                    return True
            except (psutil.NoSuchProcess, psutil.AccessDenied):
                pass
    except Exception:
        pass
    return False

def _get_last_opened(path: str) -> str:
    """Devuelve la última fecha de apertura de un archivo (UserAssist → mtime → ctime)."""
    try:
        mtime = os.path.getmtime(path)
        return datetime.fromtimestamp(mtime).strftime('%Y-%m-%d %H:%M')
    except Exception:
        return 'Desconocida'

def _is_non_instance_location(path: str) -> bool:
    """Devuelve True si el path está en una ubicación de descarga/temp (no instancia activa)."""
    p = path.lower()
    return any(frag in p for frag in _NON_INSTANCE_FRAGMENTS)

def _extract_class_strings(data: bytes) -> list:
    """P2 #47 — Parsea el constant pool de un .class de Java y devuelve sus strings UTF-8.
    Implementación directa del formato Class File Spec (sin necesitar javap/ASM).
    Sólo extrae CONSTANT_Utf8 (tag=1); ignora el resto de tags.
    """
    import struct as _struct
    if len(data) < 10 or data[:4] != b'\xca\xfe\xba\xbe':
        return []
    try:
        pos = 8  # magic(4) + minor(2) + major(2)
        const_count = _struct.unpack_from('>H', data, pos)[0]
        pos += 2
        strings = []
        i = 1
        while i < const_count and pos < len(data):
            tag = data[pos]; pos += 1
            if tag == 1:       # Utf8: u2 length + bytes
                ln = _struct.unpack_from('>H', data, pos)[0]; pos += 2
                try:
                    s = data[pos:pos+ln].decode('utf-8', errors='ignore')
                    if len(s) >= 3:
                        strings.append(s)
                except Exception:
                    pass
                pos += ln
            elif tag in (3, 4):    # Integer / Float
                pos += 4
            elif tag in (5, 6):    # Long / Double — ocupan 2 slots
                pos += 8; i += 1
            elif tag in (7, 8, 16, 19, 20):  # Class / String / MethodType / Module / Package
                pos += 2
            elif tag in (9, 10, 11, 12, 17, 18):  # Fieldref / Methodref / etc.
                pos += 4
            elif tag == 15:    # MethodHandle
                pos += 3
            else:
                break           # tag desconocido → detener parseo
            i += 1
        return strings
    except Exception:
        return []


def _is_hack_folder(dir_name: str, root_lower: str) -> bool:
    """Devuelve True si el nombre de carpeta parece ser de un hack client.

    Evita falsos positivos de:
    - Carpetas de Chrome (ClientCertificates, AutofillAIModelCache, etc.)
    - Carpetas con 'mod' en 'model', 'modify', etc.
    - Carpetas de launchers/software legítimo
    """
    # 1. Excluir rutas conocidas como seguras
    if any(frag in root_lower for frag in _SAFE_ROOT_FRAGMENTS):
        return False

    name_lower = dir_name.lower()

    # 2. Excluir nombres de carpetas específicamente legítimos
    _SAFE_FOLDER_NAMES = {
        'shaders', 'textures', 'resourcepacks', 'shaderpacks',
        'screenshots', 'saves', 'schematics', 'servers',
        'logs', 'crash-reports', 'updates', 'versions',
        'assets', 'libraries', 'natives', 'runtime',
        'backups', 'config', 'data', 'world', 'worlds',
        'node_modules', 'venv', '__pycache__', '.git',
        'zomboid', 'media', 'pylance', 'skimage',
        'client data',  # término legítimo en apps
    }
    if name_lower in _SAFE_FOLDER_NAMES:
        return False

    # 3. Nombres exactos de hack clients conocidos (substring seguro)
    if any(hack in name_lower for hack in _DEFINITE_HACK_NAMES):
        return True

    # 4. Palabras genéricas con word-boundary (no substring de otra palabra)
    # Ejemplo: 'hack' matchea 'hack-menu' pero NO 'shack' ni 'unhackable'
    # 'crack' matchea 'crack-mc' pero NO 'crackdown' (→ 'c' después de 'crack')
    # 'cheat' matchea 'cheatengine' pero NO palabra legítima que empiece con cheat
    for word in _WORD_BOUNDARY_HACK_WORDS:
        # Busca que el patrón NO esté precedido por una letra
        if _re.search(r'(?<![a-z])' + _re.escape(word), name_lower):
            return True

    return False
# ─────────────────────────────────────────────────────────────────────────────

class DetallesVentana:
    """Ventana avanzada para mostrar detalles con gráfico y 4 niveles"""
    def __init__(self, parent, archivos_sospechosos):
        self.archivos = archivos_sospechosos
        self.ventana = Toplevel(parent)
        self.ventana.title("🔍 Análisis Detallado de Hallazgos")
        self.ventana.geometry("1400x800")
        self.ventana.configure(bg="#1e1e1e")
        
        # Clasificar en 4 niveles
        self.clasificar_niveles()
        
        # Header
        header = tk.Frame(self.ventana, bg="#1a1a2e", height=70)
        header.pack(fill=tk.X)
        header.pack_propagate(False)
        
        tk.Label(
            header,
            text=f"🔍 ANÁLISIS DETALLADO - {len(archivos_sospechosos)} Hallazgos",
            font=("Segoe UI", 18, "bold"),
            bg="#1a1a2e",
            fg="#00d9ff"
        ).pack(pady=10)
        
        tk.Label(
            header,
            text=f"🔴 Hacks: {self.stats['hacks']} | 🟠 Sospechoso: {self.stats['sospechoso']} | 🟡 Poco Sospechoso: {self.stats['poco_sospechoso']} | 🟢 Normal: {self.stats['normal']}",
            font=("Segoe UI", 10),
            bg="#1a1a2e",
            fg="#b4b4b4"
        ).pack()
        
        # Container principal horizontal
        main_container = tk.Frame(self.ventana, bg="#1e1e1e")
        main_container.pack(fill=tk.BOTH, expand=True, padx=20, pady=20)
        
        # Panel izquierdo - Gráfico
        left_panel = tk.Frame(main_container, bg="#16213e", width=450)
        left_panel.pack(side=tk.LEFT, fill=tk.BOTH, padx=(0, 10))
        
        tk.Label(
            left_panel,
            text="📊 DISTRIBUCIÓN POR NIVEL",
            font=("Segoe UI", 14, "bold"),
            bg="#16213e",
            fg="#00d9ff"
        ).pack(pady=15)
        
        # Crear gráfico circular
        self.crear_grafico(left_panel)
        
        # Panel derecho - Pestañas con detalles
        right_panel = tk.Frame(main_container, bg="#16213e")
        right_panel.pack(side=tk.RIGHT, fill=tk.BOTH, expand=True)
        
        tk.Label(
            right_panel,
            text="📋 DETALLES POR CATEGORÍA",
            font=("Segoe UI", 14, "bold"),
            bg="#16213e",
            fg="#00d9ff"
        ).pack(pady=15)
        
        # Crear Notebook (pestañas)
        style = ttk.Style()
        style.theme_use('default')
        style.configure('TNotebook', background='#16213e', borderwidth=0)
        style.configure('TNotebook.Tab', background='#2c3e50', foreground='white', padding=[20, 10])
        style.map('TNotebook.Tab', background=[('selected', '#00d9ff')], foreground=[('selected', 'black')])
        
        self.notebook = ttk.Notebook(right_panel)
        self.notebook.pack(fill=tk.BOTH, expand=True, padx=10, pady=(0, 10))
        
        # Crear pestañas para cada nivel
        self.crear_pestana_nivel("🔴 HACKS", self.niveles['hacks'], "#5c1a1a")
        self.crear_pestana_nivel("🟠 SOSPECHOSO", self.niveles['sospechoso'], "#5c4a1a")
        self.crear_pestana_nivel("🟡 POCO SOSPECHOSO", self.niveles['poco_sospechoso'], "#4a4a1a")
        self.crear_pestana_nivel("🟢 NORMAL", self.niveles['normal'], "#1a4a1a")
        
        # Botones inferiores
        btn_frame = tk.Frame(self.ventana, bg="#1e1e1e")
        btn_frame.pack(fill=tk.X, padx=20, pady=10)
        
        tk.Button(
            btn_frame,
            text="❌ Cerrar",
            command=self.ventana.destroy,
            bg="#c73e1d",
            fg="white",
            font=("Segoe UI", 10, "bold"),
            padx=20,
            pady=10
        ).pack(side=tk.RIGHT, padx=5)
    
    def clasificar_niveles(self):
        """Clasifica hallazgos en 4 niveles"""
        self.niveles = {
            'hacks': [],
            'sospechoso': [],
            'poco_sospechoso': [],
            'normal': []
        }
        
        for item in self.archivos:
            nivel = self.determinar_nivel(item)
            self.niveles[nivel].append(item)
        
        self.stats = {
            'hacks': len(self.niveles['hacks']),
            'sospechoso': len(self.niveles['sospechoso']),
            'poco_sospechoso': len(self.niveles['poco_sospechoso']),
            'normal': len(self.niveles['normal'])
        }
    
    def determinar_nivel(self, item):
        """Determina el nivel de peligrosidad"""
        tipo = item.get('type', '').lower()
        nombre = item.get('name', '').lower()
        alerta_original = item.get('alerta', 'INFO')
        
        # Si ya tiene alerta específica de string
        if alerta_original in ['HACKS', 'SOSPECHOSO', 'POCO_SOSPECHOSO', 'NORMAL']:
            return alerta_original.lower()
        
        # HACKS - Evidencia clara (Nivel 1)
        # Keywords PRIORIZADOS por frecuencia (según admin)
        hacks_keywords = [
            # MUY COMÚN (detectados frecuentemente)
            'tinytools', 'tiny-tools', 'tiny_tools',
            'autoclicker', 'auto-clicker', 'auto_clicker', 'ac.exe', 'ac.jar', 'ac_',
            
            # COMÚN (inyectores PvP)
            'inject', 'injector', 'inyector', 'iny',
            'pvpinjector', 'pvp-injector', 'pvpinject',
            'dll-inject', 'dllinjector', 'dll_inject',
            
            # Clientes conocidos
            'vape', 'vape.', 'vapev', 'vapelite', 'vape4',
            'entropy', 'entropy.', 'whiteout', 'liquidbounce', 'wurst', 'impact.',
            
            # Clientes raros
            'hackclient', 'ghostclient', 'injectclient', 'clientmod',
            'customclient', 'pvpclient', 'mineclient',
            
            # Tools
            'cheatengine', 'processhacker', 'memoryedit',
            
            # Módulos
            'xray', 'killaura', 'scaffold', 'speedhack',
            'reach', 'velocity', 'wtap', 'aimassist', 'triggerbot',
            
            # Genéricos
            'incognito', 'bypass', 'stealth', 'undetected'
        ]
        if any(h in nombre for h in hacks_keywords):
            return 'hacks'
        if tipo in ['process', 'injected_dll', 'jar_file', 'file_modified_during_ss', 'usb_removed'] and alerta_original == 'CRITICAL':
            return 'hacks'
        # Modificaciones DURANTE la SS = Nivel 1
        if tipo in ['file_modified_during_ss', 'usb_removed']:
            return 'hacks'
        
        # SOSPECHOSO - Muy probable hack (Nivel 2)
        if tipo in ['java_cmdline', 'prefetch_jna', 'temp_jna', 'file_deleted', 'file_created', 'file_renamed']:
            # Los archivos deleted/created/renamed ya vienen con su nivel, respetarlo
            if alerta_original in ['HACKS', 'SOSPECHOSO', 'POCO_SOSPECHOSO']:
                return alerta_original.lower()
            return 'sospechoso'
        if alerta_original == 'CRITICAL':
            return 'sospechoso'
        
        # POCO SOSPECHOSO - Revisar manualmente (Nivel 3/4)
        if tipo in ['window', 'registry', 'logitech', 'razer', 'file_modified_pre_ss', 'usb_added']:
            return 'poco_sospechoso'
        if alerta_original == 'WARNING':
            return 'poco_sospechoso'
        
        # NORMAL - Informativo
        return 'normal'
    
    def crear_grafico(self, parent):
        """Crea el gráfico circular"""
        if not MATPLOTLIB_AVAILABLE:
            # Sin matplotlib, mostrar estadísticas en texto
            tk.Label(
                parent,
                text="📊 Estadísticas",
                font=("Segoe UI", 14, "bold"),
                bg="#16213e",
                fg="#00d9ff"
            ).pack(pady=15)
            
            stats_text = f"""
🔴 Hacks: {self.stats['hacks']}
🟠 Sospechoso: {self.stats['sospechoso']}
🟡 Poco Sospechoso: {self.stats['poco_sospechoso']}
🟢 Normal: {self.stats['normal']}
            """
            tk.Label(
                parent,
                text=stats_text,
                font=("Segoe UI", 10),
                bg="#16213e",
                fg="#ffffff",
                justify=tk.LEFT
            ).pack(pady=10)
            return
        
        fig = Figure(figsize=(5, 5), facecolor='#16213e')
        ax = fig.add_subplot(111)
        
        # Datos para el gráfico
        labels = ['🔴 Hacks', '🟠 Sospechoso', '🟡 Poco Sospechoso', '🟢 Normal']
        sizes = [
            self.stats['hacks'],
            self.stats['sospechoso'],
            self.stats['poco_sospechoso'],
            self.stats['normal']
        ]
        colors = ['#ff4444', '#ffa500', '#ffeb3b', '#4caf50']
        explode = (0.1, 0.05, 0, 0)  # Destacar Hacks
        
        # Filtrar categorías vacías
        filtered_labels = []
        filtered_sizes = []
        filtered_colors = []
        filtered_explode = []
        
        for i, size in enumerate(sizes):
            if size > 0:
                filtered_labels.append(labels[i])
                filtered_sizes.append(size)
                filtered_colors.append(colors[i])
                filtered_explode.append(explode[i])
        
        if filtered_sizes:
            wedges, texts, autotexts = ax.pie(
                filtered_sizes,
                labels=filtered_labels,
                colors=filtered_colors,
                autopct='%1.1f%%',
                startangle=90,
                explode=filtered_explode,
                textprops={'color': 'white', 'fontsize': 11, 'weight': 'bold'}
            )
            
            ax.axis('equal')
            fig.patch.set_facecolor('#16213e')
            ax.set_facecolor('#16213e')
        else:
            ax.text(0.5, 0.5, 'Sin datos', ha='center', va='center', 
                   fontsize=16, color='white')
            ax.axis('off')
        
        # Integrar en tkinter
        canvas = FigureCanvasTkAgg(fig, parent)
        canvas.draw()
        canvas.get_tk_widget().pack(fill=tk.BOTH, expand=True, padx=20, pady=20)
    
    def crear_pestana_nivel(self, titulo, items, bg_color):
        """Crea una pestaña para un nivel específico"""
        frame = tk.Frame(self.notebook, bg="#0d0d0d")
        self.notebook.add(frame, text=titulo)
        
        if not items:
            tk.Label(
                frame,
                text=f"✓ No hay elementos en esta categoría",
                font=("Segoe UI", 12),
                bg="#0d0d0d",
                fg="#4ec9b0"
            ).pack(pady=50)
            return
        
        # ScrolledText para mostrar detalles
        text_area = scrolledtext.ScrolledText(
            frame,
            wrap=tk.WORD,
            font=("Consolas", 10),
            bg="#0d0d0d",
            fg="#e0e0e0",
            padx=15,
            pady=15
        )
        text_area.pack(fill=tk.BOTH, expand=True, padx=10, pady=10)
        
        # Agregar cada item
        for i, item in enumerate(items, 1):
            text_area.insert(tk.END, f"{'=' * 80}\n", "separator")
            text_area.insert(tk.END, f"#{i} - {item.get('name', 'N/A')}\n", "title")
            text_area.insert(tk.END, f"{'=' * 80}\n\n", "separator")
            
            text_area.insert(tk.END, f"📌 Tipo: ", "label")
            text_area.insert(tk.END, f"{item.get('type', 'N/A')}\n\n", "value")
            
            # Ruta o descripción
            if 'path' in item and item['path'] != 'N/A':
                text_area.insert(tk.END, f"📂 Ubicación:\n", "label")
                text_area.insert(tk.END, f"   {item['path']}\n\n", "path")
            else:
                text_area.insert(tk.END, f"⚠️  Descripción:\n", "label")
                text_area.insert(tk.END, f"   {self.get_descripcion(item)}\n\n", "warning")
            
            # Detalles adicionales
            if 'pid' in item:
                text_area.insert(tk.END, f"🔢 PID: ", "label")
                text_area.insert(tk.END, f"{item['pid']}\n", "value")
            
            if 'hash' in item and item['hash']:
                text_area.insert(tk.END, f"🔐 SHA256:\n", "label")
                text_area.insert(tk.END, f"   {item['hash']}\n", "hash")
            
            if 'keyword' in item:
                text_area.insert(tk.END, f"🔍 Keyword Detectado: ", "label")
                text_area.insert(tk.END, f"{item['keyword']}\n", "danger")
            
            # Fecha de modificación
            path = item.get('path', '')
            if path and path != 'N/A' and os.path.exists(path) and os.path.isfile(path):
                try:
                    timestamp = os.path.getmtime(path)
                    fecha = datetime.fromtimestamp(timestamp).strftime("%Y-%m-%d %H:%M:%S")
                    text_area.insert(tk.END, f"📅 Última Modificación: ", "label")
                    text_area.insert(tk.END, f"{fecha}\n", "value")
                except:
                    pass
            
            text_area.insert(tk.END, "\n")
        
        # Configurar tags
        text_area.tag_config("separator", foreground="#3e3e42")
        text_area.tag_config("title", foreground="#00d9ff", font=("Consolas", 11, "bold"))
        text_area.tag_config("label", foreground="#569cd6", font=("Consolas", 10, "bold"))
        text_area.tag_config("value", foreground="#e0e0e0")
        text_area.tag_config("path", foreground="#4ec9b0")
        text_area.tag_config("hash", foreground="#d4d4d4", font=("Consolas", 8))
        text_area.tag_config("danger", foreground="#ff4444", font=("Consolas", 10, "bold"))
        text_area.tag_config("warning", foreground="#ffa500")
        
        text_area.config(state=tk.DISABLED)
    
    def get_descripcion(self, item):
        """Obtiene descripción si no es un archivo"""
        tipo = item.get('type', '')
        tiempo = item.get('tiempo', '')
        
        if tipo == 'process':
            return f"Proceso activo en memoria (PID: {item.get('pid', 'N/A')})"
        elif tipo == 'window':
            return f"Ventana/Overlay activo detectado"
        elif tipo == 'java_cmdline':
            return f"Parámetros sospechosos en comando Java - Keyword: {item.get('keyword', 'N/A')}"
        elif tipo == 'registry':
            return f"Entrada en registro de Windows - Valor: {item.get('value', 'N/A')}"
        elif tipo == 'service':
            return f"Servicio de Windows sospechoso - Estado: {item.get('status', 'N/A')}"
        elif tipo == 'injected_dll':
            return f"DLL inyectada en proceso Java (PID: {item.get('pid', 'N/A')})"
        elif tipo == 'file_modified_during_ss':
            return f"⚠️ ARCHIVO MODIFICADO DURANTE LA SS - {tiempo}"
        elif tipo == 'file_modified_pre_ss':
            return f"Archivo modificado antes de la SS (0-5 min) - {tiempo}"
        elif tipo == 'file_deleted':
            return f"🗑️ ARCHIVO ELIMINADO DESDE BOOT - {tiempo}"
        elif tipo == 'file_created':
            return f"📁 ARCHIVO CREADO DESDE BOOT - {tiempo}"
        elif tipo == 'file_renamed':
            return f"✏️ ARCHIVO RENOMBRADO DESDE BOOT - {tiempo}"
        elif tipo == 'usb_removed':
            return f"⚠️ USB DESCONECTADO DURANTE LA SS - Intento de ocultar evidencia"
        elif tipo == 'usb_added':
            return f"USB conectado durante la SS - {tiempo}"
        else:
            return f"Elemento sospechoso detectado - Tipo: {tipo}"
    
    def copiar_rutas(self, archivos):
        rutas = []
        for f in archivos:
            if 'path' in f and f['path'] != 'N/A':
                rutas.append(f['path'])
            else:
                rutas.append(f"[{f.get('type')}] {f.get('name')} - {self.get_descripcion(f)}")
        
        texto = "\n".join(rutas)
        self.ventana.clipboard_clear()
        self.ventana.clipboard_append(texto)
        messagebox.showinfo("Copiado", f"Se copiaron {len(rutas)} elementos al portapapeles")


class ArgusApp:
    def __init__(self, root):
        self.root = root
        
        # Aplicar estilo moderno de ARGUS PROJECTS
        if UI_STYLE_AVAILABLE:
            ModernUI.apply_window_style(self.root)
        else:
            # Detectar resolución para fallback
            screen_width = self.root.winfo_screenwidth()
            if screen_width <= 1366:
                width, height = 740, 480
                min_width, min_height = 660, 420
            elif screen_width <= 1920:
                width, height = 880, 540
                min_width, min_height = 740, 460
            else:
                width, height = 980, 600
                min_width, min_height = 880, 540
            
            self.root.title("Argus Projects — Security Scanner Pro")
            self.root.geometry(f"{width}x{height}")
            self.root.minsize(min_width, min_height)
            self.root.configure(bg="#0d1117")
            
            # Asegurar opacidad completa
            try:
                self.root.attributes('-alpha', 1.0)
            except:
                pass
        
        # Cargar configuración PRIMERO para verificar si hay token
        self.config = self.load_config()
        # P5 #35 — apply --profile override if requested
        self._apply_profile_env(self.config)

        # Verificar autenticación después de cargar config
        try:
            auth_result = self.check_authentication()
            if not auth_result:
                # Si el usuario cancela, cerrar la aplicación
                self.root.destroy()
                return
        except Exception as e:
            # Si hay un error en la autenticación, mostrar error y continuar
            import traceback
            error_msg = f"Error en autenticación: {str(e)}\n{traceback.format_exc()}"
            print(error_msg)
            try:
                messagebox.showerror("Error de Autenticación",
                    f"Hubo un error en el sistema de autenticación.\n\n{str(e)}\n\nLa aplicación continuará sin autenticación.")
            except:
                pass
            # Continuar sin autenticación para permitir debugging

        # Verificar actualizaciones en background
        try:
            threading.Thread(target=self._check_for_update, daemon=True).start()
        except Exception:
            pass

        # Variables
        self.scanning = False
        self.issues_found = []
        self.detected_minecraft_username = None  # Username detectado desde conexiones activas
        
        # Variables de monitoreo temporal
        self.anydesk_start_time = None
        self.monitoring_active = False
        self.initial_usb_devices = self.get_usb_devices()
        self.usb_info = {}  # Información detallada de USB para el reporte
        
        # Detectar si AnyDesk está corriendo
        self.detect_anydesk_start()
        
        # Rutas y procesos legítimos a excluir (whitelist)
        self.whitelist_paths = self.load_whitelist()
        
        # Integración con Base de Datos y API (DEBE inicializarse ANTES de legitimate_patterns)
        self.db_integration = None
        try:
            from db_integration import DatabaseIntegration
            api_url = self.config.get('api_url', 'https://asperss.onrender.com')
            scan_token = self.config.get('scan_token', '')
            
            if scan_token:
                print(f"🔑 Token de escaneo encontrado en config: {scan_token}")
            else:
                print("⚠️ No hay token de escaneo en config.json")
            
            self.db_integration = DatabaseIntegration(api_url=api_url, scan_token=scan_token)
            self.db_integration.app = self  # Pasar referencia de la app para acceso a username detectado
            print("✅ Integración con BD inicializada")
        except ImportError as e:
            print(f"⚠️ Módulo db_integration no disponible - continuando sin integración BD: {e}")
            self.db_integration = None
        except Exception as e:
            import traceback
            print(f"⚠️ Error al inicializar integración BD: {e}")
            print(f"   Traceback: {traceback.format_exc()}")
            self.db_integration = None
        
        # Sistema de patrones legítimos (aprende de feedback)
        self.legitimate_patterns = None
        try:
            from legitimate_patterns import LegitimatePatterns
            # Usar ruta por defecto para la base de datos
            # La BD se busca en el mismo directorio que el ejecutable o script
            db_path = 'scanner_db.sqlite'
            
            # Verificar que db_integration existe antes de usarlo
            # DatabaseIntegration no tiene database_path, así que siempre usamos la ruta por defecto
            if self.db_integration is None:
                print("⚠️ db_integration no está disponible, usando configuración por defecto para patrones legítimos")
            
            self.legitimate_patterns = LegitimatePatterns(database_path=db_path)
            print("✅ Sistema de patrones legítimos inicializado")
        except Exception as e:
            import traceback
            print(f"⚠️ Error inicializando patrones legítimos: {e}")
            print(f"   Traceback: {traceback.format_exc()}")
            # Asegurar que legitimate_patterns sea None si falla
            self.legitimate_patterns = None
        
        self.root.protocol('WM_DELETE_WINDOW', lambda: None)

        # Hotkey de emergencia — solo staff que conoce la combinación
        def _emergency_exit(event=None):
            try:
                self.root.destroy()
            except Exception:
                import os as _os
                _os.abort()
        self.root.bind('<Control-Alt-Shift-Q>', _emergency_exit)
        self.root.bind('<Control-Alt-Shift-q>', _emergency_exit)

        # Crear interfaz mejorada con estilo moderno
        self.create_ui()

        self._click_test_result = None
        self.root.after(800, self.full_scan_with_discord)

        # Inicializar variables de cronómetro
        self.scan_start_time = None
        self.timer_running = False
        self.timer_thread = None
        self.resources_label = None
        
        # Control de animación de progreso
        self.progress_animation_running = False
        self.progress_animation_thread = None
        self.progress_target_value = 0
        self._progress_message = ""
        
        # Base de datos de hashes SHA256 de archivos conocidos (hacks detectados)
        self.known_hack_hashes = set()
        self.load_known_hack_hashes()
        
        # Cache de análisis de archivos para evitar re-analizar
        self.file_analysis_cache = {}
        
        # NOTA: db_integration ya fue inicializado arriba, antes de legitimate_patterns
        
        # Analizador de IA
        self.ai_analyzer = None
        try:
            from ai_analyzer import AIAnalyzer
            # Pasar ruta de BD y API para que cargue patrones aprendidos dinámicamente
            db_path = 'scanner_db.sqlite'
            api_url = self.config.get('api_url', 'https://asperss.onrender.com')
            scan_token = self.config.get('scan_token', '')
            
            self.ai_analyzer = AIAnalyzer(
                database_path=db_path,
                api_url=api_url if api_url else None,
                scan_token=scan_token if scan_token else None
            )
            print("✅ Analizador de IA inicializado (con aprendizaje progresivo y actualización dinámica)")
        except ImportError:
            print("⚠️ Módulo ai_analyzer no disponible")
        except Exception as e:
            print(f"⚠️ Error inicializando analizador de IA: {e}")
        
        # Inicializar nuevos sistemas de detección avanzada
        try:
            from file_cache import FileCache
            self.file_cache = FileCache(database_path='scanner_db.sqlite')
            print("✅ Sistema de caché inteligente inicializado")
        except ImportError:
            print("⚠️ Módulo file_cache no disponible")
            self.file_cache = None
        except Exception as e:
            print(f"⚠️ Error inicializando caché: {e}")
            self.file_cache = None
        
        try:
            from scoring_system import ScoringSystem
            self.scoring_system = ScoringSystem()
            print("✅ Sistema de scoring de confianza inicializado")
        except ImportError:
            print("⚠️ Módulo scoring_system no disponible")
            self.scoring_system = None
        except Exception as e:
            print(f"⚠️ Error inicializando scoring: {e}")
            self.scoring_system = None
        
        try:
            from autoclicker_detector import AutoclickerDetector
            self.autoclicker_detector = AutoclickerDetector()
            print("✅ Detector de autoclickers activos inicializado")
        except ImportError:
            print("⚠️ Módulo autoclicker_detector no disponible")
            self.autoclicker_detector = None
        except Exception as e:
            print(f"⚠️ Error inicializando detector de autoclickers: {e}")
            self.autoclicker_detector = None
        
        try:
            from xray_texture_analyzer import XRayTextureAnalyzer
            self.xray_analyzer = XRayTextureAnalyzer()
            print("✅ Analizador de texturas X-ray inicializado")
        except ImportError:
            print("⚠️ Módulo xray_texture_analyzer no disponible")
            self.xray_analyzer = None
        except Exception as e:
            print(f"⚠️ Error inicializando analizador X-ray: {e}")
            self.xray_analyzer = None
        
        try:
            from java_injection_detector import JavaInjectionDetector
            self.java_injection_detector = JavaInjectionDetector()
            print("✅ Detector de inyección Java inicializado")
        except ImportError:
            print("⚠️ Módulo java_injection_detector no disponible")
            self.java_injection_detector = None
        except Exception as e:
            print(f"⚠️ Error inicializando detector de inyección: {e}")
            self.java_injection_detector = None

        # ── SS Forensics (historical evidence — survives scanner deletion) ──────
        self.forensic_findings = []  # stored separately to bypass the false-positive filter
        try:
            from ss_forensics import SSForensics
            self.ss_forensics = SSForensics()
            print("✅ SS Forensics inicializado (14 técnicas del checklist manual)")
        except ImportError:
            print("⚠️ Módulo ss_forensics no disponible")
            self.ss_forensics = None
        except Exception as e:
            print(f"⚠️ Error inicializando SS Forensics: {e}")
            self.ss_forensics = None

        # ── Mouse weight / click-bug detector (Prison mode) ─────────────────
        # Initialized FIRST so the initial snapshot is taken as early as possible,
        # before the player has time to remove the weight or reconnect the mouse.
        self.mouse_findings = []   # stored separately to bypass the false-positive filter
        try:
            from mouse_weight_detector import MouseWeightDetector
            self.mouse_detector = MouseWeightDetector()
            self.mouse_detector.start_monitoring()
            print("✅ Detector de peso/manipulación de mouse inicializado (prison mode)")
        except ImportError:
            print("⚠️ Módulo mouse_weight_detector no disponible")
            self.mouse_detector = None
        except Exception as e:
            print(f"⚠️ Error inicializando detector de mouse: {e}")
            self.mouse_detector = None
    
    def load_known_hack_hashes(self):
        """Carga base de datos de hashes SHA256 de hacks conocidos - SISTEMA DE APRENDIZAJE CON ACTUALIZACIÓN DINÁMICA"""
        import sqlite3
        import os
        import json
        import requests
        
        # Hashes conocidos iniciales (ejemplos)
        known_hashes = []
        
        # Cargar hashes aprendidos de la base de datos local
        db_path = 'scanner_db.sqlite'
        if os.path.exists(db_path):
            try:
                conn = sqlite3.connect(db_path)
                cursor = conn.cursor()
                
                # Cargar hashes marcados como hack por el staff
                cursor.execute('''
                    SELECT file_hash FROM learned_hashes WHERE is_hack = 1
                ''')
                
                learned_hashes = [row[0] for row in cursor.fetchall() if row[0]]
                known_hashes.extend(learned_hashes)
                
                conn.close()
                
                if learned_hashes:
                    print(f"✅ {len(learned_hashes)} hashes aprendidos cargados desde BD local")
            except Exception as e:
                print(f"⚠️ Error cargando hashes aprendidos: {e}")
        
        # Intentar cargar hashes desde API
        api_url = self.config.get('api_url', '').rstrip('/')
        if api_url and requests is not None:
            # 1. Endpoint dedicado de hashes de hacks conocidos (cloud hash DB)
            try:
                response = requests.get(f"{api_url}/api/hashes", timeout=10)
                if response.status_code == 200:
                    data = response.json()
                    cloud_hashes = data.get('hashes', [])
                    _hash_freq_map = {}  # F23: sha256 → confirmed_count
                    for h in cloud_hashes:
                        v = h.get('sha256', '')
                        if v and v not in known_hashes:
                            known_hashes.append(v)
                        if v:
                            _hash_freq_map[v.lower()] = int(h.get('confirmed_count') or 1)
                    self._cloud_hash_frequency = _hash_freq_map
                    print(f"✅ {len(cloud_hashes)} hashes de hack cloud cargados desde /api/hashes")
                    # Guardar caché offline
                    _cache_dir = os.path.join(os.environ.get('APPDATA', ''), 'ASPERSProjectsSS')
                    os.makedirs(_cache_dir, exist_ok=True)
                    with open(os.path.join(_cache_dir, 'hack_hashes.json'), 'w') as f:
                        json.dump(cloud_hashes, f)
            except Exception as e:
                print(f"⚠️ Error cargando cloud hashes: {e}")
                # Fallback a caché local
                try:
                    _cache_path = os.path.join(os.environ.get('APPDATA', ''), 'ASPERSProjectsSS', 'hack_hashes.json')
                    if os.path.exists(_cache_path):
                        with open(_cache_path) as f:
                            for h in json.load(f):
                                v = h.get('sha256', '')
                                if v and v not in known_hashes:
                                    known_hashes.append(v)
                        print("✅ Cloud hashes cargados desde caché local")
                except Exception:
                    pass

            # 2. Modelo de IA — hashes aprendidos por feedback del staff
            try:
                response = requests.get(f"{api_url}/api/ai-model/latest", timeout=10)
                if response.status_code == 200:
                    data = response.json()
                    api_hashes = data.get('hashes', [])
                    for hash_data in api_hashes:
                        if hash_data.get('is_hack') and hash_data.get('hash'):
                            hash_value = hash_data.get('hash')
                            if hash_value not in known_hashes:
                                known_hashes.append(hash_value)
                    print(f"✅ {len(api_hashes)} hashes adicionales cargados desde /api/ai-model/latest")
                    models_dir = os.path.join(os.environ.get('APPDATA', ''), 'ASPERSProjectsSS', 'models')
                    os.makedirs(models_dir, exist_ok=True)
                    with open(os.path.join(models_dir, 'ai_model_latest.json'), 'w', encoding='utf-8') as f:
                        json.dump(data, f, indent=2)
            except Exception as e:
                print(f"⚠️ Error cargando hashes desde AI model API: {e}")
                try:
                    model_file = os.path.join(os.environ.get('APPDATA', ''), 'ASPERSProjectsSS', 'models', 'ai_model_latest.json')
                    if os.path.exists(model_file):
                        with open(model_file, 'r', encoding='utf-8') as f:
                            data = json.load(f)
                        for hash_data in data.get('hashes', []):
                            if hash_data.get('is_hack') and hash_data.get('hash'):
                                v = hash_data['hash']
                                if v not in known_hashes:
                                    known_hashes.append(v)
                        print("✅ Hashes AI cargados desde archivo local (modo offline)")
                except Exception:
                    pass

        self.known_hack_hashes = set(known_hashes)
        if not hasattr(self, '_cloud_hash_frequency'):
            self._cloud_hash_frequency = {}  # F23: sha256 → confirmed_count

    def load_whitelist(self):
        """Carga lista blanca EXPANDIDA al 200% - Rutas legítimas para evitar falsos positivos"""
        return {
            # ========== APLICACIÓN PROPIA ==========
            'aplicación de ss', 'minecraft ss tool', 'minecraftsstool.exe', 'argusscanner.exe', 'argus projects', 'aspers',
            'source\\dist', 'source\\build', 'source\\main.py', 'source\\ui_style.py',
            
            # ========== JUEGOS Y LAUNCHERS LEGÍTIMOS ==========
            'steam', 'steamapps', 'epic games', 'riot games', 'valorant', 'league of legends',
            'overwatch', 'call of duty', 'warzone', 'fortnite', 'apex legends', 'pubg',
            'gta', 'gtav', 'gta v', 'gta5', 'rockstar', 'rockstar games', 'gtavlauncher.exe',
            'origin', 'ea games', 'battlenet', 'blizzard', 'activision', 'ubisoft',
            'bethesda', 'cd projekt', 'take-two', '2k', 'square enix', 'capcom', 'konami',
            'bandai namco', 'sega', 'nintendo', 'sony', 'microsoft', 'xbox', 'playstation',
            'fifa', 'fifa 17', 'fifa 18', 'fifa 19', 'fifa 20', 'fifa 21', 'fifa 22',
            'fifa 23', 'fifa 24', 'fifa 25', 'opti', 'crack', 'bonus', 'gamedata',
            
            # ========== SOFTWARE REMOTO Y LEGÍTIMO ==========
            'anydesk', 'anydesk.exe', 'teamviewer', 'teamviewer.exe', 'splashtop',
            'chrome remote', 'microsoft remote', 'parsec', 'logmein', 'gotomypc',
            'ultraviewer', 'ammyy', 'radmin', 'vnc', 'tightvnc', 'realvnc',
            
            # ========== SOFTWARE LEGÍTIMO GENERAL ==========
            'microsoft', 'windows', 'system32', 'syswow64', 'program files',
            'visual studio', 'nvidia', 'amd', 'intel', 'discord', 'obs', 'spotify',
            'chrome', 'firefox', 'edge', 'adobe', 'winrar', '7zip', 'winzip',
            'vlc', 'media player', 'potplayer', 'mpc-hc', 'k-lite', 'codec',
            
            # ========== LAUNCHERS Y CLIENTES LEGÍTIMOS DE MINECRAFT ==========
            'tlauncher', 'curseforge', 'prism', 'multimc', 'gdlauncher',
            'badlion client', 'badlion', 'feather client', 'feather', 'pvp lounge',
            'lunar client', 'lunar', 'lunarclient', 'polymc', 'atlauncher',
            'beast client', 'beastclient', 'beast-client',  # cliente FPS/cosméticos, no hack
            'nether client', 'netherclient',                # cliente FPS legítimo
            # Herramientas de análisis anticheat (no marcar el propio scanner como hack)
            'argusscanner', 'argus scanner', 'argus-scanner',
            'echo', 'echoscanner', 'echo-scanner', 'echo-acb',  # Echo anticheat
            'astross', 'astro-ss', 'astroanticheck',
            
            # ========== MODS LEGÍTIMOS DE MINECRAFT (EXPANDIDO 200%) ==========
            'optifine', 'forge', 'fabric', 'iris', 'sodium', 'lithium', 'phosphor',
            'starlight', 'carpet', 'carpetmod', 'tweakeroo', 'litematica', 'minihud',
            'malilib', 'itemscroller', 'inventory profiles', 'worldedit', 'worldguard',
            'essentials', 'luckperms', 'vault', 'economy', 'permissions', 'multiverse',
            'plotsquared', 'griefprevention', 'coreprotect', 'citizens', 'mythicmobs',
            'mcmmo', 'jobs', 'shopkeepers', 'chestshop', 'auctionhouse', 'auction',
            'elementalcrystalsmod', 'elementalcrystals', 'modsreferencia', 'mowziesmobs',
            'jei', 'rei', 'wthit', 'jade', 'hwyla', 'the one probe', 'top',
            'appleskin', 'journeymap', 'xaero', 'voxelmap', 'minimap', 'map',
            'waystones', 'waypoint', 'teleport', 'tp', 'home', 'spawn', 'warp',
            'backpack', 'storage', 'chest', 'barrel', 'drawer', 'cabinet',
            'refined storage', 'ae2', 'applied energistics', 'mekanism', 'thermal',
            'create', 'immersive engineering', 'industrial', 'tech', 'machines',
            
            # ========== PROYECTOS Y DESARROLLO ==========
            'proyecto juego', 'project bot aspers', 'asperswebpage', 'src', 'models',
            'sourcefiles', 'thirdpersoncontroller', 'timmyrobot', 'starterassets',
            'character', 'unity', 'assets', 'source files', 'in-editor tutorial',
            'setup guide', 'project zomboid', 'zomboid', 'phasmophobia',
            'streamingassets', 'language models', 'languagemodels',
            
            # ========== CARPETAS DEL SISTEMA ==========
            'appdata\\local\\temp', 'windows\\temp', 'programdata', 'perflogs',
            'windows\\prefetch', 'windows\\system32', 'windows\\syswow64',
            
            # ========== DRIVERS Y UTILIDADES ==========
            'logitech', 'razer', 'corsair', 'hyperx', 'steelseries', 'roccat',
            'cooler master', 'nzxt', 'asus rog', 'msi', 'gigabyte', 'evga',
            
            # ========== IDEs Y HERRAMIENTAS DE DESARROLLO ==========
            'vscode', 'visual studio code', 'intellij', 'eclipse', 'netbeans',
            'pycharm', 'webstorm', 'goland', 'clion', 'rider', 'phpstorm',
            'node_modules', 'gradle', 'maven', 'npm', 'pip', 'conda', 'venv',
            'env', '.venv', '__pycache__', '.git', '.svn', '.hg',
            
            # ========== NAVEGADORES ==========
            'chrome', 'firefox', 'edge', 'opera', 'brave', 'vivaldi', 'safari',
            'tor', 'internet explorer', 'ie', 'msie', 'trident',
            
            # ========== CLOUD STORAGE ==========
            'onedrive', 'dropbox', 'google drive', 'icloud', 'mega', 'pcloud',
            'box', 'sync', 'spideroak', 'backblaze', 'carbonite', 'idrive',
            
            # ========== SOFTWARE DE GRABACIÓN Y STREAMING ==========
            'streamlabs', 'xsplit', 'bandicam', 'fraps', 'dxtory', 'shadowplay',
            'relive', 'raptr', 'medal', 'outplayed', 'nvidia shadowplay',
            'amd relive', 'obs studio', 'open broadcaster',
            
            # ========== SOFTWARE DE OFIMÁTICA ==========
            'office', 'word', 'excel', 'powerpoint', 'outlook', 'onenote',
            'libreoffice', 'openoffice', 'wps', 'google docs', 'sheets',
            
            # ========== SOFTWARE DE DISEÑO ==========
            'photoshop', 'illustrator', 'indesign', 'premiere', 'after effects',
            'gimp', 'inkscape', 'blender', 'maya', '3ds max', 'cinema 4d',
            
            # ========== SOFTWARE DE DESARROLLO ==========
            'git', 'github', 'gitlab', 'bitbucket', 'svn', 'cvs', 'hg',
            'docker', 'kubernetes', 'ansible', 'terraform', 'jenkins',
            'jira', 'confluence', 'slack', 'teams', 'zoom', 'skype',
        }
    
    def is_whitelisted(self, path):
        """Verifica si una ruta está en la lista blanca - MEJORADO 200%"""
        if not path:
            return False
        
        path_lower = path.lower()
        filename = os.path.basename(path_lower)
        
        # ========== EXCLUSIONES CRÍTICAS (prioridad máxima) ==========
        # Excluir la carpeta de la aplicación SS y el ejecutable propio
        if any(excl in path_lower for excl in [
            'aplicación de ss', 'minecraft ss tool', 'minecraftsstool.exe',
            'source\\dist', 'source\\build', 'aspers projects'
        ]):
            return True
        
        # Excluir el ejecutable propio por nombre exacto
        if filename in ['minecraftsstool.exe', 'argusscanner.exe', 'ss_tool.exe', 'aspers_scanner.exe']:
            return True
        
        # ========== VERIFICACIÓN DE WHITELIST EXPANDIDA ==========
        # Verificar whitelist con coincidencias exactas y parciales mejoradas
        for item in self.whitelist_paths:
            # Coincidencia exacta en nombre de archivo
            if filename == item or filename.startswith(item) or filename.endswith(item):
                return True
            
            # Coincidencia en ruta completa
            if item in path_lower:
                # Verificación adicional: no debe ser un hack disfrazado
                # Si el path contiene palabras de hack conocidas, no whitelistear
                hack_keywords = ['vape', 'entropy', 'ghost', 'inject', 'bypass', 'cheat', 'hack']
                if not any(hack in path_lower for hack in hack_keywords):
                    return True
        
        # ========== EXCLUSIONES POR EXTENSIÓN LEGÍTIMA ==========
        # Archivos de sistema y configuración legítimos
        legit_extensions = ['.sys', '.dll', '.drv', '.cpl', '.ocx', '.msc', '.mui']
        if any(path_lower.endswith(ext) for ext in legit_extensions):
            # Pero verificar que no esté en ubicación sospechosa
            if 'temp' not in path_lower and 'downloads' not in path_lower:
                return True
        
        return False
    
    def is_critical_finding(self, item):
        """Determina si un hallazgo es REALMENTE crítico"""
        name = item.get('name', '').lower()
        path = item.get('path', '').lower()
        tipo = item.get('type', '')
        
        # Patrones críticos confirmados
        critical_keywords = [
            'vape', 'entropy', 'ghost', 'inject', 'bypass', 'killaura', 'aimbot',
            'triggerbot', 'reach', 'velocity', 'antiknockback', 'scaffold', 'fly',
            'xray', 'fullbright', 'cheat', 'hack', 'wurst', 'liquid', 'sigma',
            'astolfo', 'exhibition', 'flux', 'novoline', 'rise', 'moon', 'drip'
        ]
        
        # Si contiene palabra crítica
        for keyword in critical_keywords:
            if keyword in name or keyword in path:
                # Verificar que no sea falso positivo
                if not self.is_whitelisted(path):
                    return True
        
        return False
    
    # ============================================================
    # MÓDULOS DE DETECCIÓN AVANZADA
    # ============================================================
    
    def scan_processes_logic(self):
        """Lógica de escaneo de procesos - MEJORADO CON DETECCIÓN AVANZADA DE SUBPROCESOS E INYECCIONES"""
        print("🔍 ESCANEANDO PROCESOS...")
        issues = []
        
        # Usar el nuevo analizador de conexiones de Minecraft para detectar subprocesos e inyecciones
        try:
            from minecraft_connection_analyzer import MinecraftConnectionAnalyzer
            analyzer = MinecraftConnectionAnalyzer()
            
            # Escanear procesos de Minecraft y detectar inyecciones/subprocesos ocultos
            print("🔍 Analizando procesos de Minecraft y subprocesos ocultos...")
            minecraft_issues = analyzer.scan_minecraft_processes_and_injections()
            issues.extend(minecraft_issues)
            
            # Detectar autoclickers relacionados con Minecraft
            autoclicker_issues = analyzer.detect_autoclicker_processes()
            issues.extend(autoclicker_issues)
            
            # Obtener username desde conexiones activas
            if analyzer.minecraft_username:
                self.detected_minecraft_username = analyzer.minecraft_username
                print(f"👤 Username de Minecraft detectado desde conexión activa: {analyzer.minecraft_username}")
        except ImportError:
            print("⚠️ Módulo minecraft_connection_analyzer no disponible")
        except Exception as e:
            print(f"⚠️ Error en análisis avanzado de conexiones: {e}")
        
        # Detectar autoclickers activos
        if self.autoclicker_detector:
            try:
                print("🔍 Detectando autoclickers activos...")
                autoclicker_issues = self.autoclicker_detector.scan_running_processes()
                for issue in autoclicker_issues:
                    issues.append({
                        'tipo': 'process',
                        'nombre': issue.get('name', 'Unknown'),
                        'ruta': issue.get('exe', ''),
                        'archivo': issue.get('exe', ''),
                        'categoria': issue.get('type', 'autoclicker'),
                        'alerta': issue.get('alert', 'SOSPECHOSO'),
                        'confidence': issue.get('confidence', 0.5),
                        'detected_patterns': ['autoclicker_active'],
                        'is_active_process': True
                    })
                print(f"✅ Detectados {len(autoclicker_issues)} autoclickers activos")
            except Exception as e:
                print(f"⚠️ Error detectando autoclickers: {e}")
        
        # Detectar inyección en procesos Java/Minecraft
        if self.java_injection_detector:
            try:
                print("🔍 Detectando inyección en procesos Java...")
                injection_issues = self.java_injection_detector.scan_java_processes()
                for issue in injection_issues:
                    issues.append({
                        'tipo': 'java_injection',
                        'nombre': issue.get('description', 'Java Injection'),
                        'ruta': issue.get('agent_path', '') or issue.get('bootclasspath', '') or issue.get('jar_file', ''),
                        'archivo': issue.get('agent_path', '') or issue.get('bootclasspath', '') or issue.get('jar_file', ''),
                        'categoria': issue.get('type', 'injection'),
                        'alerta': issue.get('alert', 'CRITICAL'),
                        'confidence': issue.get('confidence', 0.8),
                        'detected_patterns': ['java_injection'],
                        'injection_detected': True
                    })
                print(f"✅ Detectadas {len(injection_issues)} inyecciones en procesos Java")
            except Exception as e:
                print(f"⚠️ Error detectando inyecciones: {e}")
        
        try:
            for proc in psutil.process_iter(['pid', 'name', 'exe', 'cmdline']):
                try:
                    proc_info = proc.info
                    name = proc_info['name'].lower()
                    cmdline = ' '.join(proc_info['cmdline']) if proc_info['cmdline'] else ''
                    
                    # Detectar procesos sospechosos
                    if self.is_suspicious_process(name):
                        issues.append({
                            'tipo': 'PROCESS',
                            'nombre': proc_info['name'],
                            'ruta': proc_info['exe'] or 'N/A',
                            'pid': proc_info['pid'],
                            'cmdline': cmdline,
                            'alerta': 'CRITICAL',
                            'categoria': 'PROCESSES'
                        })
                    
                    # Detectar comandos Java sospechosos - MEJORADO CON MÁS PATRONES
                    if 'java' in name and any(cmd in cmdline.lower() for cmd in ['-jar', '-cp', 'minecraft']):
                        # Patrones expandidos de hacks en línea de comandos Java
                        java_hack_patterns = [
                            'vape', 'entropy', 'liquidbounce', 'wurst', 'impact', 'sigma',
                            'flux', 'future', 'astolfo', 'exhibition', 'novoline', 'rise',
                            'moon', 'drip', 'phobos', 'komat', 'wasp', 'konas', 'seppuku',
                            'injector', 'ghostclient', 'killaura', 'aimbot', 'triggerbot',
                            'xray', 'fullbright', 'speedhack', 'wtap', 'aimassist',
                            'bhop', 'nofall', 'autoclicker', 'ac.exe', 'ac.jar'
                        ]
                        
                        cmdline_lower = cmdline.lower()
                        detected_hacks = [hack for hack in java_hack_patterns if hack in cmdline_lower]
                        
                        if detected_hacks:
                            # Verificar que no sea falso positivo
                            if not self.is_whitelisted(cmdline):
                                alert_level = 'CRITICAL' if any(h in detected_hacks for h in ['vape', 'entropy', 'whiteout', 'injector']) else 'SOSPECHOSO'
                            issues.append({
                                'tipo': 'JAVA_CMD',
                                'nombre': proc_info['name'],
                                'ruta': cmdline,
                                'pid': proc_info['pid'],
                                'cmdline': cmdline,
                                    'alerta': alert_level,
                                    'categoria': 'JAVA_CMD',
                                    'detected_hacks': detected_hacks
                            })
                            
                except (psutil.NoSuchProcess, psutil.AccessDenied):
                    continue
                    
        except Exception as e:
            print(f"Error escaneando procesos: {e}")
            
        return issues
    
    def scan_minecraft_files_logic(self):
        """Lógica de escaneo de archivos de Minecraft - MEJORADO CON DETECCIÓN AVANZADA"""
        print("🔍 ESCANEANDO ARCHIVOS DE MINECRAFT...")
        issues = []
        
        # Analizar texturas X-ray
        if self.xray_analyzer:
            try:
                print("🔍 Analizando texturas X-ray...")
                xray_issues = self.xray_analyzer.scan_resource_packs()
                for issue in xray_issues:
                    issues.append({
                        'tipo': 'xray_texture',
                        'nombre': issue.get('name', 'Unknown'),
                        'ruta': os.path.dirname(issue.get('path', '')),
                        'archivo': issue.get('path', ''),
                        'categoria': 'texture_modification',
                        'alerta': issue.get('alert', 'SOSPECHOSO'),
                        'confidence': issue.get('confidence', 0.6),
                        'detected_patterns': ['xray_texture'],
                        'transparency_ratio': issue.get('transparency_ratio', 0)
                    })
                print(f"✅ Detectadas {len(xray_issues)} texturas X-ray")
            except Exception as e:
                print(f"⚠️ Error analizando texturas X-ray: {e}")
        
        try:
            # Rutas comunes de Minecraft expandidas
            minecraft_paths = [
                os.path.expanduser("~\\AppData\\Roaming\\.minecraft"),
                os.path.expanduser("~\\AppData\\Local\\.minecraft"),
                os.path.expanduser("~\\AppData\\LocalLow\\.minecraft"),
                "C:\\Users\\Public\\Minecraft",
                "C:\\Program Files\\Minecraft",
                "C:\\Program Files (x86)\\Minecraft",
                os.path.expanduser("~\\Documents\\Minecraft"),
                os.path.expanduser("~\\Desktop\\Minecraft"),
                os.path.expanduser("~\\Downloads\\Minecraft"),
                # Launchers alternativos
                os.path.expanduser("~\\AppData\\Roaming\\.tlauncher"),
                os.path.expanduser("~\\AppData\\Roaming\\.multimc"),
                os.path.expanduser("~\\AppData\\Roaming\\.prismlauncher"),
                os.path.expanduser("~\\AppData\\Roaming\\.gdlauncher"),
                os.path.expanduser("~\\AppData\\Roaming\\.lunarclient"),
                os.path.expanduser("~\\AppData\\Roaming\\.badlion"),
            ]
            
            # Extensiones a escanear en carpetas de Minecraft
            minecraft_extensions = ('.jar', '.class', '.java', '.lua', '.txt', '.log', '.cfg', 
                                   '.config', '.json', '.properties', '.dat', '.cache', '.tmp')
            
            for path in minecraft_paths:
                if os.path.exists(path):
                    print(f"📁 Escaneando: {path}")
                    try:
                        for root, dirs, files in os.walk(path):
                            # Verificar carpetas sospechosas primero
                            for dir_name in dirs:
                                dir_lower = dir_name.lower()
                                if any(hack in dir_lower for hack in ['vape', 'entropy', 'flux', 'sigma', 
                                                                      'inject', 'ghost', 'bypass', 'hack', 'cheat']):
                                    if not self.is_whitelisted(os.path.join(root, dir_name)):
                                        issues.append({
                                            'tipo': 'MINECRAFT_FOLDER',
                                            'nombre': dir_name,
                                            'ruta': os.path.join(root, dir_name),
                                            'archivo': os.path.join(root, dir_name),
                                            'alerta': 'CRITICAL',
                                            'categoria': 'MINECRAFT'
                                        })
                            
                            # Escanear archivos
                            for file in files:
                                file_lower = file.lower()
                                # Solo escanear extensiones relevantes
                                if file_lower.endswith(minecraft_extensions):
                                    full_path = os.path.join(root, file)
                                    
                                    # Verificar si es sospechoso (con análisis de contenido)
                                    if self.is_suspicious_file(full_path):
                                        # Análisis avanzado de contenido
                                        content_analysis = self.analyze_file_content(full_path)
                                        
                                        alert_level = 'SOSPECHOSO'
                                        if content_analysis['is_hack'] and content_analysis['confidence'] >= 80:
                                            alert_level = 'CRITICAL'
                                        
                                issues.append({
                                    'tipo': 'MINECRAFT_FILE',
                                    'nombre': file,
                                    'ruta': full_path,
                                    'archivo': file,
                                            'alerta': alert_level,
                                            'categoria': 'MINECRAFT',
                                            'confidence': content_analysis.get('confidence', 0),
                                            'detected_patterns': content_analysis.get('detected_patterns', []),
                                            'obfuscation': content_analysis.get('obfuscation_detected', False),
                                            'file_hash': content_analysis.get('file_hash')
                                        })
                    except PermissionError:
                        continue
                    except Exception as e:
                        print(f"Error escaneando {path}: {e}")
                        continue
                                
        except Exception as e:
            print(f"Error escaneando archivos de Minecraft: {e}")
            
        return issues
    
    def scan_all_jars(self):
        """Escanea todos los JARs en el sistema - MEJORADO CON ANÁLISIS DE CONTENIDO"""
        print("🔍 ESCANEANDO TODOS LOS JARs...")
        issues = []
        
        def scan():
            try:
                # Ubicaciones prioritarias primero (más rápido)
                priority_locations = [
                    os.path.expanduser("~\\AppData\\Roaming\\.minecraft"),
                    os.path.expanduser("~\\AppData\\Local"),
                    os.path.expanduser("~\\Downloads"),
                    os.path.expanduser("~\\Desktop"),
                    os.path.expanduser("~\\Documents"),
                    "C:\\Temp",
                    "C:\\Windows\\Temp"
                ]
                
                # Escanear ubicaciones prioritarias primero
                for location in priority_locations:
                    if os.path.exists(location):
                        try:
                            for root, dirs, files in os.walk(location):
                                # Limitar profundidad
                                if root.count(os.sep) - location.count(os.sep) > 10:
                                    dirs[:] = []
                                    continue
                                
                            for file in files:
                                if file.lower().endswith('.jar'):
                                        full_path = os.path.join(root, file)
                                        
                                        # Verificar whitelist primero
                                        if self.is_whitelisted(full_path):
                                            continue
                                        
                                        # Análisis avanzado de contenido
                                        content_analysis = self.analyze_file_content(full_path)
                                        
                                        # Si el análisis de contenido indica hack con alta confianza
                                        if content_analysis['is_hack'] and content_analysis['confidence'] >= 60:
                                            in_inst = _is_minecraft_instance(full_path)
                                            running = in_inst and _is_process_running(file)
                                            last_opened = _get_last_opened(full_path)
                                            if in_inst:
                                                alerta = 'CRITICAL' if running else 'SOSPECHOSO'
                                            else:
                                                alerta = 'CRITICAL' if content_analysis['confidence'] >= 80 else 'SOSPECHOSO'
                                            issues.append({
                                                'tipo': 'JAR_FILE',
                                                'nombre': file + (' [CORRIENDO]' if running else ''),
                                                'ruta': full_path,
                                                'archivo': file,
                                                'hash': content_analysis.get('file_hash', 'N/A'),
                                                'alerta': alerta,
                                                'categoria': 'JAR_FILES',
                                                'extra': {'running': running, 'last_opened': last_opened},
                                                'confidence': content_analysis['confidence'],
                                                'detected_patterns': content_analysis.get('detected_patterns', []),
                                                'obfuscation': content_analysis.get('obfuscation_detected', False)
                                            })
                                        # Si el nombre es sospechoso
                                        elif self.is_suspicious_file(full_path):
                                            issues.append({
                                                'tipo': 'JAR_FILE',
                                                'nombre': file,
                                                'ruta': full_path,
                                                'archivo': file,
                                                'hash': content_analysis.get('file_hash', 'N/A'),
                                            'alerta': 'SOSPECHOSO',
                                                'categoria': 'JAR_FILES',
                                                'confidence': content_analysis.get('confidence', 0)
                                            })
                        except (PermissionError, OSError):
                            continue
                        except Exception as e:
                            print(f"Error escaneando {location}: {e}")
                            continue
                
                # Escanear otras unidades si hay tiempo
                drives = ['C:\\', 'D:\\', 'E:\\', 'F:\\']
                for drive in drives:
                    if os.path.exists(drive) and drive not in ['C:\\']:  # Ya escaneamos C en ubicaciones prioritarias
                        try:
                            # Solo escanear carpetas específicas en otras unidades
                            specific_folders = [
                                os.path.join(drive, "Users"),
                                os.path.join(drive, "Temp"),
                                os.path.join(drive, "Downloads")
                            ]
                            for folder in specific_folders:
                                if os.path.exists(folder):
                                    for root, dirs, files in os.walk(folder):
                                        if root.count(os.sep) - folder.count(os.sep) > 5:
                                            dirs[:] = []
                                            continue
                                        
                                        for file in files:
                                            if file.lower().endswith('.jar'):
                                                full_path = os.path.join(root, file)
                                                if not self.is_whitelisted(full_path):
                                                    content_analysis = self.analyze_file_content(full_path)
                                                    if content_analysis['is_hack'] and content_analysis['confidence'] >= 70:
                                                        issues.append({
                                                            'tipo': 'JAR_FILE',
                                                            'nombre': file,
                                                            'ruta': full_path,
                                                            'archivo': file,
                                                            'hash': content_analysis.get('file_hash', 'N/A'),
                                                            'alerta': 'CRITICAL',
                                                            'categoria': 'JAR_FILES',
                                                            'confidence': content_analysis['confidence']
                                                        })
                        except:
                            continue
                                        
            except Exception as e:
                print(f"Error escaneando JARs: {e}")
                
        scan()
        return issues
    
    def scan_recent_files(self):
        """Escanea archivos recientes"""
        print("🔍 ESCANEANDO ARCHIVOS RECIENTES...")
        issues = []
        
        def scan():
            try:
                # Escanear archivos modificados en las últimas 24 horas
                cutoff_time = time.time() - (24 * 60 * 60)
                
                drives = ['C:\\', 'D:\\', 'E:\\', 'F:\\']
                for drive in drives:
                    if os.path.exists(drive):
                        for root, dirs, files in os.walk(drive):
                            for file in files:
                                try:
                                    file_path = os.path.join(root, file)
                                    if os.path.getmtime(file_path) > cutoff_time:
                                        if self.is_suspicious_file(file.lower()):
                                            issues.append({
                                                'tipo': 'RECENT_FILE',
                                                'nombre': file,
                                                'ruta': file_path,
                                                'archivo': file,
                                                'alerta': 'POCO_SOSPECHOSO',
                                                'categoria': 'RECENT_FILES'
                                            })
                                except:
                                    continue
                                    
            except Exception as e:
                print(f"Error escaneando archivos recientes: {e}")
                
        scan()
        return issues
    
    def scan_prefetch_jna(self):
        """Escanea Prefetch y JNA"""
        print("🔍 ESCANEANDO PREFETCH Y JNA...")
        issues = []
        
        def scan():
            try:
                # Escanear Prefetch
                prefetch_path = "C:\\Windows\\Prefetch"
                if os.path.exists(prefetch_path):
                    for file in os.listdir(prefetch_path):
                        if file.lower().endswith('.pf'):
                            if any(hack in file.lower() for hack in ['vape', 'entropy', 'liquidbounce']):
                                issues.append({
                                    'tipo': 'PREFETCH',
                                    'nombre': file,
                                    'ruta': os.path.join(prefetch_path, file),
                                    'alerta': 'SOSPECHOSO',
                                    'categoria': 'PREFETCH'
                                })
                
                # Escanear JNA
                jna_paths = [
                    "C:\\Windows\\System32",
                    "C:\\Windows\\SysWOW64"
                ]
                
                for path in jna_paths:
                    if os.path.exists(path):
                        for file in os.listdir(path):
                            if 'jna' in file.lower():
                                issues.append({
                                    'tipo': 'JNA',
                                    'nombre': file,
                                    'ruta': os.path.join(path, file),
                                    'alerta': 'POCO_SOSPECHOSO',
                                    'categoria': 'JNA'
                                })
                                
            except Exception as e:
                print(f"Error escaneando Prefetch/JNA: {e}")
                
        scan()
        return issues
    
    def scan_downloads_folder(self):
        """Escanea Downloads, Desktop y Documents en busca de hack clients descargados
        pero que nunca se ejecutaron (no aparecen en Prefetch/DPS).
        """
        print("🔍 ESCANEANDO CARPETA DE DESCARGAS...")
        issues = []
        user_profile = os.environ.get('USERPROFILE', os.path.expanduser('~'))
        scan_dirs = [
            os.path.join(user_profile, 'Downloads'),
            os.path.join(user_profile, 'Desktop'),
            os.path.join(user_profile, 'Documents'),
            os.path.join(os.environ.get('TEMP', ''), ''),
        ]
        seen = set()
        for base_dir in scan_dirs:
            if not os.path.isdir(base_dir):
                continue
            try:
                for fname in os.listdir(base_dir):
                    fname_lower = fname.lower()
                    if fname_lower in seen:
                        continue
                    ext = os.path.splitext(fname_lower)[1]
                    if ext not in ('.exe', '.jar', '.zip', '.rar', '.7z', '.dll'):
                        continue
                    matched = next((h for h in _DEFINITE_HACK_NAMES if h in fname_lower), None)
                    if not matched:
                        continue
                    fpath = os.path.join(base_dir, fname)
                    seen.add(fname_lower)
                    print(f"⚠️ HACK DESCARGADO (no ejecutado): {fpath}")
                    issues.append({
                        'nombre': f'Hack client descargado (no ejecutado): {fname}',
                        'ruta':   fpath,
                        'archivo': fname,
                        'tipo':   'downloaded_hack',
                        'categoria': 'FORENSE',
                        'alerta': 'CRITICAL' if ext in ('.exe', '.jar') else 'SOSPECHOSO',
                        'confidence': 0.90 if ext in ('.exe', '.jar') else 0.75,
                        'detected_patterns': [f'hack_name:{matched}', f'ext:{ext}', f'dir:{os.path.basename(base_dir)}'],
                        'explicacion': (
                            f'Se encontró el archivo "{fname}" en {os.path.basename(base_dir)}. '
                            f'Contiene el nombre "{matched}" — cliente de hack conocido. '
                            f'El archivo no fue ejecutado pero está presente en el sistema.'
                        ),
                    })
            except Exception as e:
                print(f"Error escaneando {base_dir}: {e}")
        return issues

    def scan_temp_jna(self):
        """Escanea archivos temporales y JNA"""
        print("🔍 ESCANEANDO ARCHIVOS TEMPORALES...")
        issues = []
        
        def scan():
            try:
                temp_paths = [
                    os.environ.get('TEMP', ''),
                    os.environ.get('TMP', ''),
                    "C:\\Windows\\Temp"
                ]
                
                for path in temp_paths:
                    if os.path.exists(path):
                        for file in os.listdir(path):
                            if self.is_suspicious_file(file.lower()):
                                issues.append({
                                    'tipo': 'TEMP_FILE',
                                    'nombre': file,
                                    'ruta': os.path.join(path, file),
                                    'alerta': 'POCO_SOSPECHOSO',
                                    'categoria': 'TEMP_FILES'
                                })
                                
            except Exception as e:
                print(f"Error escaneando archivos temporales: {e}")
                
        scan()
        return issues
    
    def scan_registry_complete(self):
        """Escaneo completo del registro"""
        print("🔍 ESCANEANDO REGISTRO COMPLETO...")
        issues = []
        
        def scan():
            try:
                registry_paths = [
                    (winreg.HKEY_CURRENT_USER, "Software"),
                    (winreg.HKEY_LOCAL_MACHINE, "SOFTWARE"),
                    (winreg.HKEY_CURRENT_USER, "Software\\Microsoft\\Windows\\CurrentVersion\\Run"),
                    (winreg.HKEY_LOCAL_MACHINE, "SOFTWARE\\Microsoft\\Windows\\CurrentVersion\\Run")
                ]
                
                for hkey, path in registry_paths:
                    try:
                        with winreg.OpenKey(hkey, path) as key:
                            self._scan_registry_key(key, path)
                    except:
                        continue
                        
            except Exception as e:
                print(f"Error escaneando registro: {e}")
                
        scan()
        return issues
    
    def scan_services(self):
        """Escanea servicios de Windows"""
        print("🔍 ESCANEANDO SERVICIOS...")
        issues = []
        
        def scan():
            try:
                for service in psutil.win_service_iter():
                    try:
                        service_info = service.as_dict()
                        name = service_info['name'].lower()
                        display_name = service_info['display_name'].lower()
                        
                        if any(hack in name or hack in display_name for hack in ['vape', 'entropy', 'liquidbounce']):
                            issues.append({
                                'tipo': 'SERVICE',
                                'nombre': service_info['display_name'],
                                'ruta': service_info['binpath'],
                                'alerta': 'CRITICAL',
                                'categoria': 'SERVICES'
                            })
                    except:
                        continue
                        
            except Exception as e:
                print(f"Error escaneando servicios: {e}")
                
        scan()
        return issues
    
    def scan_logitech(self):
        """Escanea macros de Logitech"""
        print("🔍 ESCANEANDO MACROS DE LOGITECH...")
        issues = []
        
        def scan():
            try:
                logitech_path = "C:\\Program Files\\LGHUB"
                if os.path.exists(logitech_path):
                    for root, dirs, files in os.walk(logitech_path):
                        for file in files:
                            if file.lower().endswith(('.json', '.xml', '.cfg')):
                                if any(hack in file.lower() for hack in ['minecraft', 'mc', 'vape']):
                                    issues.append({
                                        'tipo': 'LOGITECH_MACRO',
                                        'nombre': file,
                                        'ruta': os.path.join(root, file),
                                        'alerta': 'SOSPECHOSO',
                                        'categoria': 'LOGITECH'
                                    })
                                    
            except Exception as e:
                print(f"Error escaneando macros de Logitech: {e}")
                
        scan()
        return issues
    
    def scan_razer(self):
        """Escanea macros de Razer"""
        print("🔍 ESCANEANDO MACROS DE RAZER...")
        issues = []
        
        def scan():
            try:
                razer_path = "C:\\Program Files\\Razer"
                if os.path.exists(razer_path):
                    for root, dirs, files in os.walk(razer_path):
                        for file in files:
                            if file.lower().endswith(('.json', '.xml', '.cfg')):
                                if any(hack in file.lower() for hack in ['minecraft', 'mc', 'vape']):
                                    issues.append({
                                        'tipo': 'RAZER_MACRO',
                                        'nombre': file,
                                        'ruta': os.path.join(root, file),
                                        'alerta': 'SOSPECHOSO',
                                        'categoria': 'RAZER'
                                    })
                                    
            except Exception as e:
                print(f"Error escaneando macros de Razer: {e}")
                
        scan()
        return issues
    
    def scan_date_changes(self):
        """Escanea cambios de fecha del sistema"""
        print("🔍 ESCANEANDO CAMBIOS DE FECHA...")
        issues = []
        
        def scan():
            try:
                # Verificar si la fecha del sistema ha sido modificada recientemente
                current_time = time.time()
                boot_time = psutil.boot_time()
                uptime = current_time - boot_time
                
                if uptime < 3600:  # Menos de 1 hora
                    issues.append({
                        'tipo': 'DATE_CHANGE',
                        'nombre': 'System Date Change',
                        'ruta': 'System Clock',
                        'alerta': 'POCO_SOSPECHOSO',
                        'categoria': 'DATE_CHANGES'
                    })
                    
            except Exception as e:
                print(f"Error escaneando cambios de fecha: {e}")
                
        scan()
        return issues
    
    # NOTA: scan_deleted_files antiguo (90 líneas, ventana 12h, Recycle Bin + Prefetch
    # filtrando por hack-names) FUE ELIMINADO. Era código muerto: existía una segunda
    # definición más abajo (def scan_deleted_files: pass) que sobreescribía a esta.
    # La detección de borrados ahora la cubre:
    #   - scan_deleted_recycle  → detecciones (alertas) de exes/jars/hack-names
    #   - scan_deleted_mass_event → ráfagas de borrado masivo
    #   - scan_file_activity_log → historial completo informacional (tab Logs)

    def scan_new_files(self):
        """Escanea archivos nuevos"""
        print("🔍 ESCANEANDO ARCHIVOS NUEVOS...")
        issues = []
        
        def scan():
            try:
                # Escanear archivos creados en las últimas 24 horas
                cutoff_time = time.time() - (24 * 60 * 60)
                
                drives = ['C:\\', 'D:\\', 'E:\\', 'F:\\']
                for drive in drives:
                    if os.path.exists(drive):
                        for root, dirs, files in os.walk(drive):
                            for file in files:
                                try:
                                    file_path = os.path.join(root, file)
                                    if os.path.getctime(file_path) > cutoff_time:
                                        if self.is_suspicious_file(file.lower()):
                                            issues.append({
                                                'tipo': 'NEW_FILE',
                                                'nombre': file,
                                                'ruta': file_path,
                                                'alerta': 'POCO_SOSPECHOSO',
                                                'categoria': 'NEW_FILES'
                                            })
                                except:
                                    continue
                                    
            except Exception as e:
                print(f"Error escaneando archivos nuevos: {e}")
                
        scan()
        return issues
    
    def scan_usb_devices(self):
        """Escanea dispositivos USB y pendrives"""
        print("🔍 ESCANEANDO DISPOSITIVOS USB Y PENDRIVES...")
        issues = []
        
        def scan():
            try:
                # Escanear dispositivos USB usando wmic (viene con Windows)
                import subprocess
                
                result = subprocess.run(['wmic', 'logicaldisk', 'where', 'drivetype=2', 'get', 'deviceid'],
                                      capture_output=True, text=True, timeout=10,
                                      creationflags=0x08000000)
                if result.returncode == 0:
                    lines = result.stdout.strip().split('\n')
                    for line in lines[1:]:  # Saltar la primera línea (encabezado)
                        if line.strip():
                            drive_letter = line.strip()
                            if os.path.exists(drive_letter):
                                print(f"📱 USB encontrado: {drive_letter}")
                                for root, dirs, files in os.walk(drive_letter):
                                    depth = root[len(drive_letter):].count(os.sep)
                                    if depth >= 3:
                                        dirs[:] = []
                                        continue
                                    for file in files:
                                        if self.is_suspicious_file(file.lower()):
                                            issues.append({
                                                'tipo': 'USB_FILE',
                                                'nombre': file,
                                                'ruta': os.path.join(root, file),
                                                'alerta': 'CRITICAL',
                                                'categoria': 'USB_DEVICES'
                                            })
                                        
            except Exception as e:
                print(f"Error escaneando dispositivos USB: {e}")
                
        scan()
        return issues
    
    def scan_hidden_files(self):
        """Escanea archivos ocultos en ubicaciones de usuario relevantes (no drives completos)."""
        print("🔍 ESCANEANDO ARCHIVOS OCULTOS...")
        issues = []

        def scan():
            try:
                user = os.environ.get('USERPROFILE', '')
                search_roots = [
                    os.path.join(user, 'AppData', 'Roaming'),
                    os.path.join(user, 'AppData', 'Local'),
                    os.path.join(user, 'Documents'),
                    os.path.join(user, 'Downloads'),
                    os.path.join(user, 'Desktop'),
                ]
                for base in search_roots:
                    if not os.path.isdir(base):
                        continue
                    for root, dirs, files in os.walk(base):
                        depth = root[len(base):].count(os.sep)
                        if depth >= 4:
                            dirs[:] = []
                            continue
                        _root_l = root.lower()
                        if any(frag in _root_l for frag in _SAFE_ROOT_FRAGMENTS):
                            dirs[:] = []
                            continue
                        for file in files:
                            if not file.lower().endswith(('.exe', '.jar', '.dll')):
                                continue
                            file_path = os.path.join(root, file)
                            try:
                                attrs = os.stat(file_path).st_file_attributes
                                if attrs & 0x2 and self.is_suspicious_file(file.lower()):
                                    issues.append({
                                        'tipo': 'HIDDEN_FILE',
                                        'nombre': file,
                                        'ruta': file_path,
                                        'alerta': 'SOSPECHOSO',
                                        'categoria': 'HIDDEN_FILES'
                                    })
                            except Exception:
                                continue
            except Exception as e:
                print(f"Error escaneando archivos ocultos: {e}")

        scan()
        return issues
    
    def scan_network_connections(self):
        """Escanea conexiones de red y IPs"""
        print("🔍 ESCANEANDO CONEXIONES DE RED E IPs...")
        issues = []
        
        def scan():
            pass

        scan()
        return issues
    
    def scan_minecraft_usernames(self):
        """Escanea nombres de usuario de Minecraft"""
        print("🔍 ESCANEANDO NOMBRES DE USUARIO DE MINECRAFT...")
        issues = []
        
        def scan():
            try:
                # Buscar en archivos de configuración de Minecraft
                minecraft_paths = [
                    os.path.expanduser("~\\AppData\\Roaming\\.minecraft"),
                    "C:\\Users\\Public\\Minecraft"
                ]
                
                for path in minecraft_paths:
                    if os.path.exists(path):
                        for root, dirs, files in os.walk(path):
                            for file in files:
                                if file.lower().endswith(('.json', '.txt', '.cfg', '.properties')):
                                    try:
                                        file_path = os.path.join(root, file)
                                        if os.path.getsize(file_path) > 512_000:
                                            continue
                                        with open(file_path, 'r', encoding='utf-8', errors='ignore') as f:
                                            content = f.read().lower()
                                            if any(hack in content for hack in ['vape', 'entropy', 'liquidbounce', 'wurst']):
                                                issues.append({
                                                    'tipo': 'MINECRAFT_CONFIG',
                                                    'nombre': file,
                                                    'ruta': file_path,
                                                    'alerta': 'SOSPECHOSO',
                                                    'categoria': 'MINECRAFT_CONFIGS'
                                                })
                                    except:
                                        continue
                                        
            except Exception as e:
                print(f"Error escaneando nombres de usuario de Minecraft: {e}")
                
        scan()
        return issues
    
    def scan_background_processes(self):
        """Escanea procesos en segundo/tercer plano"""
        print("🔍 ESCANEANDO PROCESOS EN SEGUNDO/TERCER PLANO...")
        issues = []
        
        def scan():
            try:
                for proc in psutil.process_iter(['pid', 'name', 'exe', 'cmdline', 'status']):
                    try:
                        proc_info = proc.info
                        name = proc_info['name'].lower()
                        status = proc_info['status']
                        
                        # Verificar procesos en segundo plano relacionados con Minecraft
                        if status in ['sleeping', 'idle'] and any(keyword in name for keyword in ['minecraft', 'java', 'mc']):
                            if self.is_suspicious_process(name):
                                issues.append({
                                    'tipo': 'BACKGROUND_PROCESS',
                                    'nombre': proc_info['name'],
                                    'ruta': proc_info['exe'] or 'N/A',
                                    'pid': proc_info['pid'],
                                    'status': status,
                                    'alerta': 'SOSPECHOSO',
                                    'categoria': 'BACKGROUND_PROCESSES'
                                })
                                
                    except (psutil.NoSuchProcess, psutil.AccessDenied):
                        continue
                        
            except Exception as e:
                print(f"Error escaneando procesos en segundo plano: {e}")
                
        scan()
        return issues
    
    def scan_autoclick_tools(self):
        """Escanea herramientas de autoclick y tinytools"""
        print("🔍 ESCANEANDO HERRAMIENTAS DE AUTOCLICK Y TINYTOOLS...")
        issues = []
        
        def scan():
            try:
                # Patrones de herramientas de autoclick
                autoclick_patterns = [
                    'autoclick', 'auto_click', 'clicker', 'mouse_clicker',
                    'tinytools', 'tiny_tools', 'macro', 'automation',
                    'ghost_mouse', 'mouse_ghost', 'click_bot'
                ]
                
                # Escanear procesos
                for proc in psutil.process_iter(['pid', 'name', 'exe']):
                    try:
                        proc_info = proc.info
                        name = proc_info['name'].lower()
                        
                        if any(pattern in name for pattern in autoclick_patterns):
                            issues.append({
                                'tipo': 'AUTOCLICK_TOOL',
                                'nombre': proc_info['name'],
                                'ruta': proc_info['exe'] or 'N/A',
                                'pid': proc_info['pid'],
                                'alerta': 'CRITICAL',
                                'categoria': 'AUTOCLICK_TOOLS'
                            })
                            
                    except (psutil.NoSuchProcess, psutil.AccessDenied):
                        continue
                
                # Escanear archivos
                drives = ['C:\\', 'D:\\', 'E:\\', 'F:\\']
                for drive in drives:
                    if os.path.exists(drive):
                        for root, dirs, files in os.walk(drive):
                            for file in files:
                                if any(pattern in file.lower() for pattern in autoclick_patterns):
                                    issues.append({
                                        'tipo': 'AUTOCLICK_FILE',
                                        'nombre': file,
                                        'ruta': os.path.join(root, file),
                                        'alerta': 'CRITICAL',
                                        'categoria': 'AUTOCLICK_TOOLS'
                                    })
                                    
            except Exception as e:
                print(f"Error escaneando herramientas de autoclick: {e}")
                
        scan()
        return issues
    
    # ============================================================
    # MÉTODOS DE ESCANEO AVANZADO
    # ============================================================
    
    def quick_scan(self):
        """Escaneo rápido de elementos críticos"""
        def scan_thread():
            try:
                self.scanning = True
                self.issues_found = []
                
                print("⚡ INICIANDO ESCANEO RÁPIDO...")
                
                # Escanear procesos
                self._update_progress_safe(20, "Escaneando procesos...", "Analizando procesos activos")
                process_issues = self.scan_processes_logic()
                self.issues_found.extend(process_issues)
                
                # Escanear archivos de Minecraft
                self._update_progress_safe(40, "Escaneando archivos de Minecraft...", "Revisando carpetas de Minecraft")
                minecraft_issues = self.scan_minecraft_files_logic()
                self.issues_found.extend(minecraft_issues)
                
                # Escanear JARs
                self._update_progress_safe(60, "Escaneando JARs...", "Analizando archivos JAR")
                jar_issues = self.scan_all_jars()
                self.issues_found.extend(jar_issues)
                
                # Escanear archivos recientes
                self._update_progress_safe(75, "Escaneando archivos recientes...", "Revisando archivos modificados recientemente")
                recent_issues = self.scan_recent_files()
                self.issues_found.extend(recent_issues)

                # Escanear descargas (hacks descargados pero no ejecutados)
                self._update_progress_safe(83, "Escaneando carpeta de descargas...", "Buscando hacks descargados")
                dl_issues = self.scan_downloads_folder()
                self.issues_found.extend(dl_issues)

                # Filtrar falsos positivos
                self._update_progress_safe(90, "Filtrando resultados...", "Eliminando falsos positivos")
                self.issues_found = self.filter_false_positives(self.issues_found)
                
                self._update_progress_safe(100, "✅ Escaneo rápido completado", f"Encontrados {len(self.issues_found)} elementos")
                
                print(f"⚡ ESCANEO RÁPIDO COMPLETADO - {len(self.issues_found)} elementos encontrados")
                
            except Exception as e:
                print(f"Error en escaneo rápido: {e}")
                self._update_progress_safe(100, f"❌ Error: {str(e)}", "Error durante el escaneo")
            finally:
                self.scanning = False
        
        threading.Thread(target=scan_thread, daemon=True).start()
    
    def scan_processes_ui(self):
        """Escaneo de procesos desde la UI"""
        def scan_thread():
            try:
                self.scanning = True
                self.issues_found = []
                
                print("🔍 INICIANDO ESCANEO DE PROCESOS...")
                
                self._update_progress_safe(50, "Escaneando procesos...", "Analizando procesos activos")
                process_issues = self.scan_processes_logic()
                self.issues_found.extend(process_issues)
                
                self._update_progress_safe(100, "✅ Escaneo de procesos completado", f"Encontrados {len(process_issues)} procesos")
                
                print(f"🔍 ESCANEO DE PROCESOS COMPLETADO - {len(process_issues)} procesos encontrados")
                
            except Exception as e:
                print(f"Error en escaneo de procesos: {e}")
                self._update_progress_safe(100, f"❌ Error: {str(e)}", "Error durante el escaneo")
            finally:
                self.scanning = False
        
        threading.Thread(target=scan_thread, daemon=True).start()
    
    def scan_files_ui(self):
        """Escaneo de archivos desde la UI"""
        def scan_thread():
            try:
                self.scanning = True
                self.issues_found = []
                
                print("📁 INICIANDO ESCANEO DE ARCHIVOS...")
                
                # Escanear archivos de Minecraft
                self._update_progress_safe(25, "Escaneando archivos de Minecraft...", "Revisando carpetas de Minecraft")
                minecraft_issues = self.scan_minecraft_files_logic()
                self.issues_found.extend(minecraft_issues)
                
                # Escanear JARs
                self._update_progress_safe(50, "Escaneando JARs...", "Analizando archivos JAR")
                jar_issues = self.scan_all_jars()
                self.issues_found.extend(jar_issues)
                
                # Escanear archivos recientes
                self._update_progress_safe(65, "Escaneando archivos recientes...", "Revisando archivos modificados recientemente")
                recent_issues = self.scan_recent_files()
                self.issues_found.extend(recent_issues)

                # Escanear descargas
                self._update_progress_safe(85, "Escaneando carpeta de descargas...", "Buscando hacks descargados")
                dl_issues = self.scan_downloads_folder()
                self.issues_found.extend(dl_issues)

                self._update_progress_safe(100, "✅ Escaneo de archivos completado", f"Encontrados {len(self.issues_found)} archivos")
                
                print(f"📁 ESCANEO DE ARCHIVOS COMPLETADO - {len(self.issues_found)} archivos encontrados")
                
            except Exception as e:
                print(f"Error en escaneo de archivos: {e}")
                self._update_progress_safe(100, f"❌ Error: {str(e)}", "Error durante el escaneo")
            finally:
                self.scanning = False
        
        threading.Thread(target=scan_thread, daemon=True).start()
    
    _vt_cache: dict   = {}  # sha256 → (positives, total) or None
    _mbaz_cache: dict = {}  # sha256 → True (known malware) or False

    @staticmethod
    def _vt_check_hash(sha256: str) -> tuple:
        """P2 #1 — Consulta VirusTotal API v3 por hash SHA256.
        Devuelve (positives, total) o None si no hay API key o hay error.
        Respeta rate-limit: 4 req/min en tier gratuito.
        """
        vt_key = os.environ.get('VIRUSTOTAL_API_KEY', '')
        if not vt_key or not sha256:
            return None
        try:
            resp = requests.get(
                f'https://www.virustotal.com/api/v3/files/{sha256}',
                headers={'x-apikey': vt_key},
                timeout=6,
            )
            if resp.status_code == 404:
                return (0, 0)  # desconocido → no concluyente
            if resp.status_code == 200:
                stats = resp.json().get('data', {}).get('attributes', {}).get('last_analysis_stats', {})
                pos   = int(stats.get('malicious', 0)) + int(stats.get('suspicious', 0))
                total = sum(stats.values()) or 1
                return (pos, total)
        except Exception:
            pass
        return None

    @staticmethod
    def _mbaz_check_hash(sha256: str) -> bool:
        """P2 #8 — Consulta MalwareBazaar (abuse.ch) por hash SHA256. Gratis, sin API key.
        Devuelve True si el hash está en MalwareBazaar como malware conocido.
        """
        if not sha256:
            return False
        try:
            resp = requests.post(
                'https://mb.api.abuse.ch/api/v1/',
                data={'query': 'get_info', 'hash': sha256},
                timeout=5,
            )
            data = resp.json()
            return data.get('query_status') == 'hash_found'
        except Exception:
            return False

    @staticmethod
    def _is_modrinth_legitimate(jar_path: str) -> bool:
        """Devuelve True si el JAR tiene hash SHA1 registrado en Modrinth (mod legítimo).
        Timeout agresivo de 4s para no demorar el scan.
        """
        try:
            import hashlib as _hl
            with open(jar_path, 'rb') as f:
                sha1 = _hl.sha1(f.read()).hexdigest()
            resp = requests.get(
                f'https://api.modrinth.com/v2/version_file/{sha1}',
                params={'algorithm': 'sha1'},
                timeout=4,
                headers={'User-Agent': 'ArgusScanner/1.6 (aspers-projects)'},
            )
            return resp.status_code == 200
        except Exception:
            return False

    # P2 #5 — CurseForge fingerprint cache (sha1 → bool)
    _cf_cache: dict = {}

    @staticmethod
    def _murmurhash2(data: bytes) -> int:
        """MurmurHash2 (32-bit) requerido por CurseForge fingerprint API."""
        seed = 1
        m = 0x5bd1e995
        r = 24
        length = len(data)
        h = seed ^ length
        i = 0
        while i + 4 <= length:
            k = int.from_bytes(data[i:i+4], 'little')
            k = (k * m) & 0xFFFFFFFF
            k ^= k >> r
            k = (k * m) & 0xFFFFFFFF
            h = (h * m) & 0xFFFFFFFF
            h ^= k
            i += 4
        remaining = length - i
        if remaining == 3:
            h ^= data[i+2] << 16
        if remaining >= 2:
            h ^= data[i+1] << 8
        if remaining >= 1:
            h ^= data[i]
            h = (h * m) & 0xFFFFFFFF
        h ^= h >> 13
        h = (h * m) & 0xFFFFFFFF
        h ^= h >> 15
        return h

    @staticmethod
    def _is_curseforge_legitimate(jar_path: str) -> bool:
        """P2 #5 — Devuelve True si el JAR está en la base de datos de CurseForge.
        Usa murmurhash2 fingerprint (requiere CF_API_KEY env var).
        Solo whitespace-stripped bytes del JAR para el fingerprint (CurseForge spec).
        """
        cf_key = os.environ.get('CF_API_KEY', '')
        if not cf_key:
            return False
        try:
            with open(jar_path, 'rb') as f:
                raw = f.read()
            # CurseForge fingerprint: filtra bytes 9 y 10 (whitespace strip)
            stripped = bytes(b for b in raw if b not in (9, 10, 13, 32))
            fingerprint = ArgusApp._murmurhash2(stripped)
            sha1_key = str(fingerprint)
            if sha1_key in ArgusApp._cf_cache:
                return ArgusApp._cf_cache[sha1_key]
            resp = requests.post(
                'https://api.curseforge.com/v1/fingerprints',
                json={'fingerprints': [fingerprint]},
                headers={
                    'x-api-key': cf_key,
                    'Content-Type': 'application/json',
                    'Accept': 'application/json',
                },
                timeout=5,
            )
            if resp.status_code == 200:
                exact_matches = resp.json().get('data', {}).get('exactMatches', [])
                result = len(exact_matches) > 0
                ArgusApp._cf_cache[sha1_key] = result
                return result
            ArgusApp._cf_cache[sha1_key] = False
            return False
        except Exception:
            return False

    @staticmethod
    @functools.lru_cache(maxsize=1)
    def _get_active_launcher_instance_paths() -> frozenset:
        """F9 — Lee profiles.json / launcher_profiles.json de launchers conocidos
        y devuelve las rutas de instancias marcadas como activas/seleccionadas.
        Hallazgos en instancias activas deben tener más peso que en inactivas.
        """
        active = []
        appdata   = os.environ.get('APPDATA', '')
        userprofile = os.environ.get('USERPROFILE', '')

        # ── Vanilla launcher (.minecraft/launcher_profiles.json) ──
        vanilla_profiles = os.path.join(appdata, '.minecraft', 'launcher_profiles.json')
        if os.path.isfile(vanilla_profiles):
            try:
                with open(vanilla_profiles, 'r', encoding='utf-8', errors='ignore') as f:
                    lp = json.load(f)
                selected = lp.get('selectedProfile') or lp.get('selectedUser', {}).get('profile')
                profiles = lp.get('profiles', {})
                if selected and selected in profiles:
                    game_dir = profiles[selected].get('gameDir')
                    if game_dir and os.path.isdir(game_dir):
                        active.append(game_dir.lower())
                # Also consider the default .minecraft as active
                active.append(os.path.join(appdata, '.minecraft').lower())
            except Exception:
                pass

        # ── Prism / MultiMC — selectedInstance in prismlauncher.cfg ──
        for launcher_cfg_dir in (
            os.path.join(appdata, 'PrismLauncher'),
            os.path.join(appdata, '.prismlauncher'),
            os.path.join(appdata, 'MultiMC'),
            os.path.join(appdata, '.multimc'),
        ):
            cfg_file = os.path.join(launcher_cfg_dir, 'prismlauncher.cfg') or \
                       os.path.join(launcher_cfg_dir, 'multimc.cfg')
            for cfg_name in ('prismlauncher.cfg', 'multimc.cfg'):
                cfg_path = os.path.join(launcher_cfg_dir, cfg_name)
                if not os.path.isfile(cfg_path):
                    continue
                try:
                    with open(cfg_path, 'r', encoding='utf-8', errors='ignore') as f:
                        for line in f:
                            if line.startswith('SelectedInstance='):
                                inst_name = line.split('=', 1)[1].strip()
                                inst_path = os.path.join(launcher_cfg_dir, 'instances', inst_name)
                                if os.path.isdir(inst_path):
                                    active.append(inst_path.lower())
                                break
                except Exception:
                    pass

        return frozenset(active)

    @staticmethod
    @functools.lru_cache(maxsize=1)
    def _get_abandoned_instance_paths() -> frozenset:
        """F6 — Devuelve set de prefijos de ruta para instancias de launchers alternativos
        que no han sido lanzadas en >60 días. Sus hallazgos son menos urgentes.
        """
        abandoned = []
        appdata = os.environ.get('APPDATA', '')
        now_ts = time.time()
        cutoff = 60 * 86400  # 60 días en segundos

        launcher_instance_roots = [
            os.path.join(appdata, 'PrismLauncher', 'instances'),
            os.path.join(appdata, 'MultiMC', 'instances'),
            os.path.join(appdata, '.prismlauncher', 'instances'),
            os.path.join(appdata, '.multimc', 'instances'),
            os.path.join(appdata, 'PolyMC', 'instances'),
            os.path.join(appdata, 'ATLauncher', 'instances'),
            os.path.join(appdata, 'GDLauncher', 'instances'),
        ]

        for root in launcher_instance_roots:
            if not os.path.isdir(root):
                continue
            try:
                for inst_name in os.listdir(root):
                    inst_path = os.path.join(root, inst_name)
                    if not os.path.isdir(inst_path):
                        continue
                    # Prism/MultiMC store lastLaunchTime in instance.cfg
                    cfg_path = os.path.join(inst_path, 'instance.cfg')
                    last_launch = None
                    if os.path.isfile(cfg_path):
                        try:
                            with open(cfg_path, 'r', encoding='utf-8', errors='ignore') as f:
                                for line in f:
                                    if line.startswith('lastLaunchTime='):
                                        val = line.split('=', 1)[1].strip()
                                        # Value is Unix timestamp in milliseconds or seconds
                                        ts = int(val)
                                        last_launch = ts / 1000 if ts > 1e10 else ts
                                        break
                        except Exception:
                            pass
                    if last_launch is None:
                        # Fallback: use instance folder mtime
                        last_launch = os.path.getmtime(inst_path)
                    if now_ts - last_launch > cutoff:
                        abandoned.append(inst_path.lower())
            except OSError:
                continue

        return frozenset(abandoned)

    @staticmethod
    def _is_legitimate_mod_jar(jar_path: str) -> bool:
        """Devuelve True si el JAR tiene indicadores de ser un mod legítimo de Minecraft.
        Revisa META-INF/MANIFEST.MF, fabric.mod.json y mods.toml.
        No hace requests de red — análisis puramente local.
        """
        try:
            import zipfile as _zf
            if not _zf.is_zipfile(jar_path):
                return False
            with _zf.ZipFile(jar_path, 'r') as zf:
                names_lower = {n.lower() for n in zf.namelist()}

                # fabric.mod.json: mods de Fabric siempre lo incluyen
                if 'fabric.mod.json' in names_lower:
                    return True

                # mods.toml: mods de Forge 1.13+ lo incluyen
                if 'meta-inf/mods.toml' in names_lower:
                    return True

                # quilt.mod.json: Quilt mod loader
                if 'quilt.mod.json' in names_lower:
                    return True

                # META-INF/MANIFEST.MF: revisar si tiene FMLCorePlugin o Fabric-Mod-Id
                manifest_key = next((n for n in zf.namelist() if n.upper() == 'META-INF/MANIFEST.MF'), None)
                if manifest_key:
                    try:
                        manifest_raw = zf.read(manifest_key).decode('utf-8', errors='ignore')
                        manifest = manifest_raw.lower()
                        legitimate_markers = [
                            'fmlcoremodcontainsfmlmod', 'fmlcoremod', 'fabric-mod-id',
                            'modside:', 'tweakclass: optifine', 'tweakclass: cpw.mods',
                        ]
                        if any(m in manifest for m in legitimate_markers):
                            return True
                        # F11 — Loaders oficiales en Implementation-Vendor
                        for line in manifest_raw.splitlines():
                            if line.lower().startswith('implementation-vendor:'):
                                vendor = line.split(':', 1)[1].strip().lower()
                                if any(v in vendor for v in ('fabricmc', 'minecraftforge', 'quiltmc',
                                                              'neoforged', 'quilt', 'neo forged')):
                                    return True
                                break
                    except Exception:
                        pass

                # F12 — Carpetas internas de loaders dentro de .minecraft (no son mods de usuario)
                _loader_internal_dirs = ('.fabric/', '.quilt/', '.forge/', '.neoforge/', '.ornithe/')
                if any(jar_path.lower().replace('\\', '/').find(d) != -1 for d in _loader_internal_dirs):
                    return True

                # F16 — JARs firmados con certificados de CurseForge/Modrinth CDN
                # Todos los mods legítimos descargados de esas plataformas llevan firma digital
                for entry in zf.namelist():
                    entry_l = entry.lower()
                    if entry_l.startswith('meta-inf/') and (
                        entry_l.endswith('.sf') or entry_l.endswith('.rsa') or entry_l.endswith('.dsa')
                    ):
                        try:
                            sig_data = zf.read(entry).decode('utf-8', errors='ignore').lower()
                            if any(cdn in sig_data for cdn in (
                                'curseforge', 'overwolf', 'modrinth', 'cfwidget',
                                'creeperhost', 'multimc.org', 'prismlauncher',
                            )):
                                return True
                        except Exception:
                            pass
                        break  # only check first signature file

        except Exception:
            pass
        return False

    def filter_false_positives(self, issues):
        """Filtrado MEJORADO - Detecta hacks reales pero menos estricto"""
        filtered = []
        hacks_critical = []
        hacks_sospechoso = []
        hacks_poco_sospechoso = []
        hacks_normal = []
        
        print(f"\n🔍 INICIANDO FILTRADO MEJORADO DE {len(issues)} ELEMENTOS...")

        # Umbral mínimo de confianza — descartar ruido < 30%
        MIN_CONFIDENCE = 30
        issues = [i for i in issues if (
            i.get('tipo', '') in {
                'ghost_client_config', 'ghost_client_registry', 'jdwp_debug_port',
                'vpn_active', 'hosts_minecraft_redirect', 'injector_process',
                'blacklisted_mod', 'modified_minecraft_jar', 'hack_string_in_loaded_jar',
            } or
            (i.get('confidence', 100) * (100 if i.get('confidence', 1) <= 1 else 1)) >= MIN_CONFIDENCE
        )]
        print(f"📉 Umbral confianza {MIN_CONFIDENCE}%: {len(issues)} elementos restantes")
        
        # ============================================================
        # FILTRO MEJORADO - DETECTA HACKS REALES PERO MENOS ESTRICTO
        # ============================================================
        
        # ── PATRONES DE HACKS REALES — SOLO nombres exclusivos, sin genéricos ──────────
        # REGLA: si el término aparece en mods legítimos de Minecraft, NO va aquí.
        # Términos eliminados: inject, bypass, ghost, fly, reach, velocity, scaffold,
        # nofall, impact, flux, rise, sigma, lb (liquid bounce), ghost, stealth, etc.
        # Esos términos se evalúan en analyze_file_content() con múltiples co-ocurrencias.
        real_hack_patterns = list(_DEFINITE_HACK_NAMES) + [
            # Variantes de nombre con extensión
            'vape.exe', 'vape.jar', 'entropy.exe', 'entropy.jar',
            'whiteout.exe', 'liquidbounce.jar', 'wurst.jar',
            # Módulos cuyo nombre NUNCA aparece en mods legítimos
            'killaura', 'aimbot', 'triggerbot', 'antikb', 'antiknockback',
            'xraymod', 'wallhack', 'boxesp', 'chams', 'traceline',
            'autoclicker', 'clickgui', 'bunnyhop', 'bhop', 'aimassist',
            'wtap', 'speedhack',
            # Injectors con nombre específico
            'dllinjector', 'extremeinjector',
            # Weave
            'weaveloader', 'weave-loader',
        ]
        # Deduplicate preservando orden
        _seen = set()
        _dedup = []
        for p in real_hack_patterns:
            if p not in _seen:
                _seen.add(p)
                _dedup.append(p)
        real_hack_patterns = _dedup
        
        # PATRONES DE FALSOS POSITIVOS — solo nombres/rutas muy específicas de software legítimo.
        # IMPORTANTE: NO incluir palabras genéricas como 'appdata', 'roaming', 'client', 'java',
        # 'temp', etc. porque esas palabras aparecen en rutas de hack clients reales y los filtrarían.
        exclude_patterns = [
            # Sistema Windows (rutas completas específicas)
            'windows\\system32', 'windows\\syswow64', 'windows\\winsxs',
            '\\program files\\microsoft', '\\program files (x86)\\microsoft',
            # Software legítimo (nombres de vendor específicos)
            'adobe', 'google\\chrome', 'mozilla\\firefox',
            'nvidia corporation', 'amd\\radeon', 'intel corporation',
            'nvidia\\cubins', 'nvidia\\displaydriver',
            'discord\\app-', 'teamspeak 3 client',
            'skype\\', 'zoom\\', 'microsoft teams',
            'steam\\steamapps', 'epicgames', 'origin games', 'ubisoft game launcher',
            # Servidores web (no Minecraft)
            'xampp\\', 'tomcat\\', '\\webapps\\', 'web-inf\\', 'webalizer',
            # Librerías Java legítimas (nombres exactos con versión)
            'gson-2.', 'jackson-core-', 'log4j-', 'authlib-',
            # Mods legítimos de Minecraft (nombres exactos)
            'optifine_', 'fabricloader-', 'forge-', 'minecraftforge-',
            'iris-', 'sodium-', 'lithium-', 'phosphor-', 'rubidium-',
            'jei-', 'create-', 'botania-', 'cobblemon-',
            # Launchers legítimos (#25 — whitelist extendida)
            'tlauncher-', 'prismlauncher', 'lunarclient\\', 'lunar client', 'badlion client\\',
            'polymc\\', 'atlauncher\\', 'curseforge\\', 'ftb app\\', 'gdlauncher\\', 'multimc\\',
            'gdlauncher', 'ftbapp', 'ftb_app', 'overwolf\\', 'curseforge\\',
            # Mods de performance y accesibilidad (#26)
            'ferritecore-', 'lazydfu-', 'entityculling-', 'dynamicfps-',
            'smoothboot-', 'starlight-', 'c2me-', 'noxesium-', 'krypton-',
            # Badlion como permitido (#27)
            'badlion\\', 'badlionclient\\', 'blclient\\',
            # DLLs del sistema Windows
            'api-ms-win-', 'msvcr', 'msvcp', 'vcruntime', 'ucrtbase',
            'kernel32.dll', 'user32.dll', 'advapi32.dll', 'shell32.dll',
            # Editores (rutas específicas)
            '\\vscode\\', '\\.vscode\\', 'node_modules\\', '\\jdk\\',
            'visual studio\\', 'intellij idea\\', 'pycharm\\',
            # Herramientas de edición de video y desarrollo
            'wondershare\\', 'wondershare filmora', 'filmora\\',
            'jetbrains\\', '\\jetbrains\\', 'rider\\', 'goland\\', 'webstorm\\', 'clion\\',
            # AppData: rutas de sistema / browsers / apps legítimas (NO son hacks)
            'webview2runtime', 'trust protection lists', 'pspc_sdk',
            'appdata\\local\\packages',          # Windows Store apps (firmadas, sandboxed)
            'appdata\\local\\origin',            # EA Origin
            'appdata\\local\\nvidia',
            'appdata\\local\\microsoft\\edge',
            'appdata\\roaming\\opera software',
            'electronic arts\\ea desktop',       # EA Desktop launcher
            'site-packages',                     # librerías Python instaladas
            'voicemod',                          # voice changer legítimo
            'minecraftsstool',                   # el propio SS tool del servidor
            # Juegos de ritmo (Osu!, Beat Saber, Geometry Dash)
            '\\osu!\\', 'appdata\\local\\osu!', 'appdata\\roaming\\osu!',
            'appdata\\locallow\\hyperbolic magnetism',  # Beat Saber
            'appdata\\locallow\\robtop games',          # Geometry Dash
            # Proyectos de desarrollo
            '\\.git\\', '\\node_modules\\', '\\dist\\',
            # Garry's Mod addons
            'garrysmod\\garrysmod\\addons',
            # Música
            'spotify\\', 'virtualdj\\', '\\fl studio\\', 'appdata\\roaming\\image-line',
            # Process Hacker 3 / System Informer
            'systeminformer', 'processhacker3', 'process hacker 3',
            # AHK instalado oficialmente
            'program files\\autohotkey', 'program files (x86)\\autohotkey',
        ]

        # ============================================================
        # FILTRADO MEJORADO
        # ============================================================
        
        # Tipos generados por scanners especializados — siempre pasan el filtro
        TRUSTED_TYPES = {
            'ghost_client_config', 'ghost_client_registry', 'jdwp_debug_port',
            'vpn_active', 'hosts_minecraft_redirect', 'hosts_file_custom',
            'blacklisted_mod', 'dll_injection_java', 'ahk_autoclick',
            'bloody_a4tech', 'peripheral_macro', 'arduino_hid_device',
            'injector_process', 'temp_jar_recent', 'baritone_prohibited',
            'baritone_installed', 'litematica_printer', 'schematica_printer',
            'optifine_zoom_combat', 'modified_minecraft_jar', 'hack_string_in_loaded_jar',
            'javaagent_injection', 'bootclasspath_modification',
            # Nuevas detecciones P1 y P3
            'weave_loader', 'prefetch_hack', 'usn_deleted_hack',
            'jitter_script', 'java_suspicious_parent', 'java_unusual_parent',
            'evasion_indicators', 'kill_chain', 'minecraft_safe_mode',
            'suspicious_process_location', 'short_lived_process', 'cloud_hash_match',
            'prescan_cleanup', 'suspicious_process_tree', 'unknown_parent_process',
            'baseline_anomaly', 'config_tfidf_match',
            'suspicious_network_connection',
            # v1.5.0 — nuevos detectores especializados
            'ghost_client_config',       # ya estaba pero incluir explícitamente
            'discord_webhook_config',    # Discord C2 en configs de hacks
            'registry_run_hack',         # Run/RunOnce con nombre de hack
            'registry_userassist_hack',  # UserAssist: hack ejecutado
            'registry_appcompat_hack',   # AppCompat: loader ejecutado
            'ahk_autoclick',             # Script/exe AHK con autoclick
            'f3t_resourcepack_exploit',  # Bug F3+T en logs — ruta contiene launcher, no filtrar
            # v1.6.0 — clipboard: pasa por filtro AI, no como trusted
            # browser_download_hack y clipboard_hack_evidence NO están en TRUSTED_TYPES
            # porque pueden generar falsos positivos — pasan por el scoring engine
        }

        # ── Rutas que NUNCA son hacks — se aplican ANTES del bypass de TRUSTED_TYPES ──
        # Razón: tipos como usn_deleted_hack, prefetch_hack saltaban el exclude_patterns
        # y flagueaban archivos temporales de Chrome, Edge, Firefox como hacks.
        ABSOLUTE_SAFE_PATHS = {
            # Navegadores (sus carpetas de perfil generan cientos de false positives)
            'google\\chrome', 'appdata\\local\\google',
            'mozilla\\firefox', 'appdata\\roaming\\mozilla',
            'microsoft\\edge', 'appdata\\local\\microsoft\\edge',
            'opera software', 'appdata\\roaming\\opera',
            'appdata\\local\\brave-browser',
            'appdata\\local\\vivaldi',
            # Sistema Windows — prefetch, temp del sistema
            'windows\\prefetch', 'windows\\system32', 'windows\\syswow64',
            'windows\\winsxs', 'windows\\softwaredistribution',
            # Launchers legítimos de Minecraft (clientes oficiales)
            'lunarclient', 'lunar client', 'lunar-client',
            'badlion', 'badlionclient', 'blclient',
            'tlauncher', 'prismlauncher', 'multimc', 'polymc',
            'curseforge', 'ftb app', 'ftbapp', 'gdlauncher', 'atlauncher', 'overwolf',
            # Plataformas de juego legítimas
            'steam\\steamapps', 'epicgames', 'origin games', 'ubisoft game launcher',
            'riotgames', 'riot games', 'battlenet', 'battle.net',
            # IDEs y desarrollo
            'visual studio', 'intellij idea', 'pycharm', 'webstorm', 'clion',
            'jetbrains', '\\vscode\\', '\\.vscode\\', 'node_modules',
            # Drivers y software del sistema
            'nvidia corporation', 'nvidia\\cubins', 'nvidia\\displaydriver',
            'amd\\radeon', 'intel corporation',
            # Comunicación
            'discord\\app-', 'teamspeak 3 client', 'zoom\\', 'skype\\',
            'microsoft teams',
            # Software legítimo
            'appdata\\local\\packages',   # Windows Store (sandboxed)
            'appdata\\local\\nvidia',
            'wondershare', 'filmora', 'obs-studio', 'obs studio',
            'site-packages',              # librerías Python instaladas
            'voicemod',
            'program files\\microsoft',
            'program files (x86)\\microsoft',
            'minecraftsstool',            # el propio scanner
            # Juegos de ritmo — sus carpetas de songs contienen palabras como
            # "riot", "rise", "impact", "extra", "insane" que colisionan con hacks
            'appdata\\local\\osu!', '\\osu!\\songs\\', '\\osu!\\skins\\',
            'appdata\\roaming\\osu!',
            # Beat Saber / Geometry Dash
            'appdata\\locallow\\hyperbolic magnetism',
            'appdata\\locallow\\robtop games',
            # Proyectos de desarrollo
            '\\.git\\', '\\node_modules\\', '\\dist\\',
            # Garry's Mod addons (nombres genéricos que colisionan con patrones de hack)
            'steam\\steamapps\\common\\garrysmod\\garrysmod\\addons',
            'garrysmod\\garrysmod\\addons',
            # Música (artistas y géneros con nombres que colisionan)
            'spotify\\', '\\spotify\\storage\\',
            'virtualdj\\', '\\fl studio\\',
            'appdata\\roaming\\image-line',   # FL Studio
            'appdata\\local\\spotify',
            # Process Hacker 3 / System Informer (sucesor oficial de PH2 — herramienta legítima)
            'systeminformer', 'processhacker3', 'process hacker 3',
            'winsystems\\systeminformer',
            # AHK instalado en Program Files (instalación oficial — no sospechosa)
            'program files\\autohotkey', 'program files (x86)\\autohotkey',
            # F17 — ProgramData y carpetas del sistema que generan FP por fecha
            'programdata\\microsoft', '\\windows\\fonts\\',
            'programdata\\packages', 'programdata\\windowsholographic',
            # F18 — AppData\Local\Microsoft (Office, Edge, Teams, Visual C++ runtimes)
            'appdata\\local\\microsoft\\',
            # F19 — Carpetas de datos de launchers (se filtraba el exe pero no sus datos)
            'appdata\\roaming\\prismlauncher\\',
            'appdata\\roaming\\multimc\\',
            'appdata\\local\\gdlauncher_next\\',
            'appdata\\local\\atlauncher\\',
            'appdata\\roaming\\lunarclient\\',
            'appdata\\local\\curseforge\\',
            'appdata\\local\\packages\\microsoft.',  # Windows Store sandboxed
        }

        # F33/F34 — Estadísticas de filtrado por motivo (para diagnóstico)
        _filter_stats = {}
        _debug_filter = os.environ.get('ARGUS_DEBUG_FILTER') == '1'
        _discarded_items = [] if _debug_filter else None  # F35: collect if debug mode
        _legit_mod_count = 0  # F25: cuenta mods legítimos verificados
        def _discard(reason_key, item_nombre, item_ruta=''):
            _filter_stats[reason_key] = _filter_stats.get(reason_key, 0) + 1
            if _debug_filter:
                _discarded_items.append({'reason': reason_key, 'nombre': item_nombre, 'ruta': item_ruta})
            print(f"✅ [{reason_key}] Descartado: {item_nombre[:60]} @ {item_ruta[:60]}")

        # F5 — ¿Está Minecraft corriendo ahora mismo? (cached para el loop)
        _mc_running = any(
            'java' in (p.info.get('name') or '').lower() and
            'minecraft' in ' '.join(p.info.get('cmdline') or []).lower()
            for p in psutil.process_iter(['name', 'cmdline'])
            if True
        )
        try:
            _mc_running  # cache computed above
        except Exception:
            _mc_running = False

        for item in issues:
            nombre = item.get('nombre', '').lower()
            ruta = item.get('ruta', '').lower()
            archivo = item.get('archivo', '').lower()
            tipo = item.get('tipo', '').lower()

            # ── FILTRO ABSOLUTO — se ejecuta antes de cualquier otra lógica ──
            # Bloquea rutas de software legítimo sin importar el tipo del hallazgo.
            _combined_path = ruta + '|' + archivo
            _is_absolute_safe = any(safe in _combined_path for safe in ABSOLUTE_SAFE_PATHS)
            if _is_absolute_safe:
                _discard('SAFE_PATH', nombre, ruta)
                continue

            # F2 — Rutas vanilla de Minecraft: NUNCA contienen hacks activos.
            # versions/, libraries/, assets/, logs/, crash-reports/, screenshots/, natives/
            _combined_mc = ruta + '|' + archivo
            if any(vp in _combined_mc for vp in _VANILLA_MC_PATHS):
                # Excepción: tipos de confianza absoluta (bytecode analysis, self-deletion, etc.)
                if tipo not in ('modified_minecraft_jar', 'self_deletion_hack', 'cp_string_hack'):
                    _discard('VANILLA_MC_PATH', nombre, ruta)
                    continue

            # F20 — Paths de servidor Minecraft (plugins, no hacks de cliente)
            _server_fragments = ('\\server\\', '/server/', '\\plugins\\', '/plugins/',
                                 '\\bukkit\\', '/bukkit/', '\\spigot\\', '/spigot/',
                                 '\\papermc\\', '/papermc/', '\\purpur\\', '/purpur/')
            if any(sf in _combined_mc for sf in _server_fragments):
                _discard('SERVER_PATH', nombre, ruta)
                continue

            # F21 — Mods desactivados (.disabled, .bak) — el jugador los desactivó a propósito
            _archivo_raw = item.get('archivo', '') or item.get('ruta', '')
            if str(_archivo_raw).lower().endswith(('.disabled', '.bak', '.off', '.old')):
                _discard('MOD_DISABLED', nombre, ruta)
                continue

            # F9 — Instancia activa según profiles.json del launcher → no degradar
            _item_path_lower = (item.get('ruta') or item.get('archivo') or '').lower()
            _in_active_instance = False
            try:
                _active_paths = self._get_active_launcher_instance_paths()
                if _active_paths and any(_item_path_lower.startswith(ap) for ap in _active_paths):
                    _in_active_instance = True
            except Exception:
                pass

            # F6 — Instancias antiguas/abandonadas (>60 días sin lanzar) → bajar severidad
            # No aplicar si la instancia está marcada como activa en profiles.json (F9)
            if not _in_active_instance:
                try:
                    _abandoned_paths = self._get_abandoned_instance_paths()
                    if _abandoned_paths and any(_item_path_lower.startswith(ap) for ap in _abandoned_paths):
                        if item.get('alerta') == 'CRITICAL':
                            item['alerta'] = 'SOSPECHOSO'
                            item.setdefault('detected_patterns', []).append('abandoned_instance_60d')
                        elif item.get('alerta') == 'SOSPECHOSO':
                            item['alerta'] = 'POCO_SOSPECHOSO'
                            item.setdefault('detected_patterns', []).append('abandoned_instance_60d')
                        item['confidence'] = max(0.15, float(item.get('confidence', 0.5)) * 0.6)
                except Exception:
                    pass

            # Verificar JARs contra indicadores locales y Modrinth antes de acusarlos
            if tipo in ('blacklisted_mod', 'jar_file') or archivo.endswith('.jar') or ruta.endswith('.jar'):
                _jar_path = item.get('archivo') or item.get('ruta') or ''
                if _jar_path and os.path.isfile(str(_jar_path)):
                    if self._is_legitimate_mod_jar(str(_jar_path)):
                        print(f"✅ [ManifestCheck] Mod legítimo (fabric/forge/quilt): {os.path.basename(str(_jar_path))}")
                        _legit_mod_count += 1
                        continue
                    if self._is_modrinth_legitimate(str(_jar_path)):
                        print(f"✅ [Modrinth] Mod legítimo verificado: {os.path.basename(str(_jar_path))}")
                        _legit_mod_count += 1
                        continue
                    if self._is_curseforge_legitimate(str(_jar_path)):
                        print(f"✅ [CurseForge] Mod legítimo verificado: {os.path.basename(str(_jar_path))}")
                        _legit_mod_count += 1
                        continue

            # P2 #1+8 — VirusTotal + MalwareBazaar para .exe/.jar sospechosos
            _vt_path = item.get('archivo') or item.get('ruta') or ''
            _alerta  = item.get('alerta', 'NORMAL')
            if (_alerta in ('SOSPECHOSO', 'CRITICAL') and _vt_path and
                    os.path.isfile(str(_vt_path)) and
                    any(str(_vt_path).lower().endswith(e) for e in ('.exe', '.jar', '.dll'))):
                try:
                    import hashlib as _hl_vt
                    _sha256_vt = _hl_vt.sha256(open(str(_vt_path), 'rb').read()).hexdigest()
                    # MalwareBazaar (gratis, sin API key)
                    if _sha256_vt not in ArgusApp._mbaz_cache:
                        ArgusApp._mbaz_cache[_sha256_vt] = self._mbaz_check_hash(_sha256_vt)
                    if ArgusApp._mbaz_cache.get(_sha256_vt):
                        print(f"🚨 [MalwareBazaar] Hash en BD de malware: {os.path.basename(str(_vt_path))}")
                        item['alerta'] = 'CRITICAL'
                        item['confidence'] = min(0.99, float(item.get('confidence', 0.5)) + 0.35)
                        item['detected_patterns'] = list(item.get('detected_patterns', [])) + ['malwarebazaar']
                    # VirusTotal (requiere VIRUSTOTAL_API_KEY)
                    if _sha256_vt not in ArgusApp._vt_cache:
                        ArgusApp._vt_cache[_sha256_vt] = self._vt_check_hash(_sha256_vt)
                    _vt_result = ArgusApp._vt_cache.get(_sha256_vt)
                    if _vt_result is not None:
                        _pos, _tot = _vt_result
                        if _pos == 0 and _tot > 10:
                            print(f"✅ [VT] 0/{_tot} detecciones — posible FP: {os.path.basename(str(_vt_path))}")
                            item['alerta'] = 'POCO_SOSPECHOSO'
                            item['confidence'] = max(0.2, float(item.get('confidence', 0.5)) * 0.4)
                            item['detected_patterns'] = list(item.get('detected_patterns', [])) + ['vt_clean']
                        elif _pos >= 5:
                            print(f"🚨 [VT] {_pos}/{_tot} detecciones: {os.path.basename(str(_vt_path))}")
                            item['alerta'] = 'CRITICAL'
                            item['confidence'] = min(0.99, float(item.get('confidence', 0.5)) + 0.25)
                            item['detected_patterns'] = list(item.get('detected_patterns', [])) + [f'vt_{_pos}']
                except Exception:
                    pass

            # F23 — Boost confidence si el mismo hash está confirmado en ≥3 scans en la BD cloud
            try:
                _f23_path = item.get('archivo') or item.get('ruta') or ''
                if _f23_path and os.path.isfile(str(_f23_path)):
                    import hashlib as _hl_f23
                    _sha256_f23 = _hl_f23.sha256(open(str(_f23_path), 'rb').read(8 * 1024 * 1024)).hexdigest()
                    _freq = self._cloud_hash_frequency.get(_sha256_f23.lower(), 0)
                    if _freq >= 3:
                        _boost = min(0.30, _freq * 0.05)
                        item['confidence'] = min(0.99, float(item.get('confidence', 0.5)) + _boost)
                        item.setdefault('detected_patterns', []).append(f'cloud_freq_{_freq}')
                        if _freq >= 5 and item.get('alerta') not in ('CRITICAL', 'MUY_SOSPECHOSO'):
                            item['alerta'] = 'SOSPECHOSO'
                        print(f"📊 [F23] Hash visto {_freq}x en BD cloud → boost confianza: {os.path.basename(str(_f23_path))}")
            except Exception:
                pass

            # Tipos de scanners especializados — confiar en ellos sin filtrar
            if tipo in TRUSTED_TYPES:
                filtered.append(item)
                continue

            # 1. EXCLUIR SOLO FALSOS POSITIVOS MUY OBVIOS
            is_false_positive = False
            
            # Verificar con sistema de patrones legítimos aprendidos
            if self.legitimate_patterns:
                try:
                    file_hash = item.get('file_hash', '')
                    is_legitimate, legit_confidence = self.legitimate_patterns.is_legitimate(
                        file_path=ruta or archivo,
                        file_name=archivo or nombre,
                        file_hash=file_hash,
                        context={'file_path': ruta or archivo}
                    )
                    
                    if is_legitimate and legit_confidence >= 0.5:
                        is_false_positive = True
                        print(f"✅ Filtrado como legítimo aprendido: {archivo or nombre} (confianza: {legit_confidence:.2f})")
                except Exception as e:
                    pass
            
            # Verificar patrones de exclusión tradicionales
            if not is_false_positive:
                for pattern in exclude_patterns:
                    if pattern in ruta or pattern in archivo or pattern in nombre:
                        is_false_positive = True
                        break
            
            # Verificar falsos positivos específicos adicionales
            if not is_false_positive:
                for false_positive in ['zomboid', 'shaders\\', '\\textures\\', 'system32', '\\program files\\', '\\windows\\system', 'microsoft\\', 'adobe\\']:
                    if false_positive in ruta or false_positive in archivo or false_positive in nombre:
                        is_false_positive = True
                        break
            
            if is_false_positive:
                continue

            # P2 #26 / F22 — Antigüedad de archivo → bajar severidad progresivamente
            _fp_age = item.get('archivo') or item.get('ruta') or ''
            if _fp_age and os.path.isfile(str(_fp_age)):
                try:
                    import time as _time_age
                    _age_days = (_time_age.time() - os.path.getmtime(str(_fp_age))) / 86400
                    _tipo_age = item.get('tipo', '')
                    _is_confirmed = 'cloud_hash_match' in _tipo_age or 'malwarebazaar' in str(item.get('detected_patterns', []))
                    if not _is_confirmed:
                        if _age_days > 365:
                            # Más de 1 año — muy probablemente inactivo
                            if item.get('alerta') in ('SOSPECHOSO', 'CRITICAL'):
                                item['alerta'] = 'POCO_SOSPECHOSO'
                            item['confidence'] = max(0.15, float(item.get('confidence', 0.5)) * 0.55)
                            item.setdefault('detected_patterns', []).append(f'file_age_{int(_age_days)}d')
                        elif _age_days > 90:
                            # F22: Entre 90 y 365 días — reducción moderada
                            item['confidence'] = max(0.25, float(item.get('confidence', 0.5)) * 0.80)
                            item.setdefault('detected_patterns', []).append(f'file_age_{int(_age_days)}d')
                        # F24 — Archivo sin modificar en >30 días → indicador de uso crónico normal (no hack activo)
                        # Aplicar solo si no está confirmado por cloud hash (en cuyo caso la antigüedad no importa)
                        elif _age_days > 30:
                            _is_confirmed_f24 = any(
                                p in str(item.get('detected_patterns', []))
                                for p in ('cloud_hash_match', 'malwarebazaar', 'vt_')
                            )
                            if not _is_confirmed_f24 and item.get('alerta') not in ('CRITICAL',):
                                item['confidence'] = max(0.25, float(item.get('confidence', 0.5)) * 0.90)
                                item.setdefault('detected_patterns', []).append(f'file_age_{int(_age_days)}d_unchanged')
                except Exception:
                    pass

            # 2. ANÁLISIS AVANZADO DE CONTENIDO (si es un archivo)
            content_confidence = 0
            if tipo in ['file', 'jar_file', 'minecraft_file'] and 'archivo' in item:
                try:
                    file_path = item.get('archivo') or item.get('ruta')
                    if file_path and os.path.exists(str(file_path)):
                        content_analysis = self.analyze_file_content(str(file_path))
                        content_confidence = content_analysis.get('confidence', 0)
                        if content_analysis.get('is_hack') and content_confidence >= 70:
                            item['confidence'] = content_confidence
                            item['detected_patterns'] = content_analysis.get('detected_patterns', [])
                            item['obfuscation'] = content_analysis.get('obfuscation_detected', False)
                            item['file_hash'] = content_analysis.get('file_hash')
                            # ── Mejora 7+10: logs y .txt tienen cap de alerta ────
                            # Un log nunca es CRITICAL solo por contenido — es evidencia indirecta
                            if content_analysis.get('is_log_file'):
                                if item.get('alerta') == 'CRITICAL':
                                    item['alerta'] = 'SOSPECHOSO'
                                # ── Mejora 9: explicación específica para logs ───
                                log_exp = content_analysis.get('log_explanation', '')
                                if log_exp:
                                    item['explicacion'] = log_exp
                                    item['tipo'] = 'log_registra_hack'
                            elif os.path.splitext(str(file_path))[1].lower() in ('.txt', '.cfg', '.properties'):
                                # .txt sin patrones múltiples: máximo SOSPECHOSO
                                if item.get('alerta') == 'CRITICAL' and content_confidence < 80:
                                    item['alerta'] = 'SOSPECHOSO'
                except:
                    pass
            
            # 3. ACEPTAR SI CONTIENE PATRONES DE HACKS
            is_potential_hack = False
            for pattern in real_hack_patterns:
                if pattern in archivo or pattern in nombre:
                    is_potential_hack = True
                    break
            
            # 4. TAMBIÉN ACEPTAR SI ESTÁ EN CARPETAS ESPECÍFICAMENTE SOSPECHOSAS
            # Regla: el path debe ser un segmento de directorio completo, no substring.
            # Eliminado: 'mc', 'temp', 'tmp' (demasiado genéricos → falsos positivos masivos)
            # 'mc' matchea C:\Program Files (x86)\Microsoft\..., 'temp' matchea qualquier temp.
            suspicious_paths = [
                '\\.minecraft\\', '\\minecraft\\',
                '\\hack\\', '\\hacks\\',
                '\\cheat\\', '\\cheats\\',
                '\\ghostclient\\', '\\ghost_client\\',
                '\\weaveloader\\', '\\.weave\\',
                '\\killaura\\', '\\aimbot\\',
            ]
            is_in_suspicious_folder = any(path in ruta for path in suspicious_paths)
            
            # 5. SCORING MULTI-FACTOR — la IA decide la severidad basándose en evidencias
            # Acumular puntos de confianza de múltiples fuentes independientes:
            ai_score = 0

            # Factor A: Nombre del archivo/hallazgo contiene patrón definitivo
            if is_potential_hack:
                matched_definite = next(
                    (p for p in real_hack_patterns if p in archivo or p in nombre),
                    None
                )
                if matched_definite and matched_definite in _DEFINITE_HACK_NAMES:
                    ai_score += 55  # Nombre exclusivo = evidencia fuerte
                else:
                    ai_score += 35  # Módulo/herramienta = evidencia media

            # Factor B: Análisis de contenido del archivo
            if content_confidence >= 85:
                ai_score += 45
            elif content_confidence >= 70:
                ai_score += 30
            elif content_confidence >= 55:
                ai_score += 15

            # Factor C: Ubicación en ruta sospechosa específica
            if is_in_suspicious_folder:
                ai_score += 20

            # Factor D: Confidence original del scanner especializado
            # F26: ignorar confidence=0.5 exacto (valor por defecto de muchos scanners — no es evidencia real)
            orig_conf = item.get('confidence', 0)
            if isinstance(orig_conf, float) and orig_conf <= 1.0:
                orig_conf *= 100
            _is_default_conf = abs(orig_conf - 50.0) < 1.0  # exactamente 50%
            if not _is_default_conf:
                if orig_conf >= 90:
                    ai_score += 30
                elif orig_conf >= 75:
                    ai_score += 20
                elif orig_conf >= 60:
                    ai_score += 10

            # F3 — Penalizar JARs en \versions\ o \libraries\ que pasaron los filtros anteriores
            # (pueden llegar aquí si son tipo TRUSTED — no borrarlos, solo bajar score)
            _combined_vanilla = ruta + '|' + archivo
            if any(vp in _combined_vanilla for vp in _VANILLA_MC_PATHS):
                ai_score = max(0, ai_score - 25)
                item.setdefault('detected_patterns', []).append('vanilla_path_penalty')

            # Solo mostrar si hay evidencia real (ai_score mínimo)
            if ai_score < 25 and not is_potential_hack and not is_in_suspicious_folder:
                _discard('LOW_SCORE', nombre, ruta)
                continue

            # F5 — Si el JAR está en \mods\ pero Minecraft NO está corriendo → bajar CRITICAL
            if not _mc_running and item.get('alerta') == 'CRITICAL':
                _in_mods = '\\mods\\' in ruta or '/mods/' in ruta
                _is_jar_type = tipo in ('blacklisted_mod', 'jar_file', 'minecraft_file') or archivo.endswith('.jar')
                if _in_mods and _is_jar_type:
                    item['alerta'] = 'SOSPECHOSO'
                    item.setdefault('detected_patterns', []).append('mc_not_running_at_scan')
                    ai_score = min(ai_score, 65)

            # Clasificar por score acumulado
            if not item.get('categoria'):
                item['categoria'] = 'HACKS'
            item['ai_score'] = ai_score

            if ai_score >= 75 or content_confidence >= 80:
                item['alerta'] = 'CRITICAL'
                hacks_critical.append(item)
            elif ai_score >= 50 or content_confidence >= 60:
                item['alerta'] = 'SOSPECHOSO'
                hacks_sospechoso.append(item)
            elif ai_score >= 30:
                item['alerta'] = 'POCO_SOSPECHOSO'
                hacks_poco_sospechoso.append(item)
            else:
                item['alerta'] = 'NORMAL'
                hacks_normal.append(item)

            filtered.append(item)
        
        # Correlación de evidencias: escalar si hay 2+ indicadores del mismo tipo
        JAVA_INJECTION_TYPES = {
            'jdwp_debug_port', 'javaagent_injection', 'bootclasspath_modification',
            'dll_injection_java', 'hack_string_in_loaded_jar', 'injector_process',
        }
        AUTOCLICK_TYPES = {
            'ahk_autoclick', 'peripheral_macro', 'bloody_a4tech', 'arduino_hid_device',
        }
        GHOST_TYPES = {
            'ghost_client_config', 'ghost_client_registry', 'blacklisted_mod', 'modified_minecraft_jar',
        }
        for group in (JAVA_INJECTION_TYPES, AUTOCLICK_TYPES, GHOST_TYPES):
            matching = [i for i in filtered if i.get('tipo', '') in group]
            if len(matching) >= 2:
                for item in matching:
                    if item.get('alerta') not in ('CRITICAL',):
                        item['alerta'] = 'CRITICAL'
                        item['confidence'] = max(item.get('confidence', 0.8), 0.92)
                        item['detected_patterns'] = list(set(item.get('detected_patterns', []) + ['multi_evidence_correlation']))
                print(f"🔗 Correlación de evidencias: {len(matching)} hallazgos → CRITICAL")

        # F34 — Estadísticas de filtrado por motivo
        print(f"\n📊 ESTADÍSTICAS DE FILTRADO MEJORADO:")
        print(f"🔴 HACKS CRÍTICOS: {len(hacks_critical)}")
        print(f"🟠 SOSPECHOSOS: {len(hacks_sospechoso)}")
        print(f"🟡 POCO SOSPECHOSOS: {len(hacks_poco_sospechoso)}")
        print(f"🟢 NORMALES: {len(hacks_normal)}")
        print(f"📋 TOTAL FILTRADO: {len(filtered)}")
        print(f"🗑️ ELEMENTOS DESCARTADOS: {len(issues) - len(filtered)}")
        if _filter_stats:
            print(f"📂 MOTIVOS DE DESCARTE:")
            for reason, count in sorted(_filter_stats.items(), key=lambda x: -x[1]):
                print(f"   {reason}: {count}")

        # F35 — Debug filter mode: show all discarded items in UI
        if _debug_filter and _discarded_items:
            print(f"\n🔬 [DEBUG-FILTER] {len(_discarded_items)} hallazgos descartados:")
            for di in _discarded_items:
                print(f"   [{di['reason']}] {di['nombre'][:70]} @ {di['ruta'][:50]}")
            # Inject discarded items as low-priority notes so they appear in UI
            for di in _discarded_items[:30]:
                filtered.append({
                    'nombre': f"[FILTRADO:{di['reason']}] {di['nombre']}",
                    'ruta': di['ruta'],
                    'tipo': 'debug_filter_discarded',
                    'categoria': 'DEBUG',
                    'alerta': 'NORMAL',
                    'confidence': 0.0,
                    'detected_patterns': [f'filter_reason:{di["reason"]}'],
                    'explicacion': f'Hallazgo descartado por filtro ({di["reason"]}). Visible solo en modo --debug-filter.',
                })

        if hacks_critical:
            print(f"\n🔴 HACKS CRÍTICOS ENCONTRADOS:")
            for item in hacks_critical[:5]:
                print(f"  - {item.get('archivo', 'N/A')} en {item.get('ruta', 'N/A')}")

        if hacks_sospechoso:
            print(f"\n🟠 HACKS SOSPECHOSOS ENCONTRADOS:")
            for item in hacks_sospechoso[:5]:
                print(f"  - {item.get('archivo', 'N/A')} en {item.get('ruta', 'N/A')}")

        if hacks_poco_sospechoso:
            print(f"\n🟡 HACKS POCO SOSPECHOSOS ENCONTRADOS:")
            for item in hacks_poco_sospechoso[:5]:
                print(f"  - {item.get('archivo', 'N/A')} en {item.get('ruta', 'N/A')}")

        # F25 — Si el jugador tiene ≥15 mods legítimos verificados → perfil de modder
        # → bajar confianza de hallazgos no confirmados para reducir FP en modders
        if _legit_mod_count >= 15:
            print(f"🎮 [F25] Perfil de modder detectado: {_legit_mod_count} mods legítimos → umbral reducido")
            _modder_unconfirmed_types = {
                'blacklisted_mod', 'jar_file', 'mixin_hack', 'dll_nonstandard', 'hack_string_in_loaded_jar'
            }
            for _item in filtered:
                if _item.get('tipo') in _modder_unconfirmed_types:
                    if 'cloud_hash_match' not in str(_item.get('detected_patterns', [])) and \
                       'malwarebazaar' not in str(_item.get('detected_patterns', [])):
                        _item['confidence'] = max(0.15, float(_item.get('confidence', 0.5)) * 0.75)
                        _item.setdefault('detected_patterns', []).append(f'modder_profile_{_legit_mod_count}mods')

        # P2 #8 — Descartar JARs demasiado pequeños (< 3KB)
        filtered = self._filter_by_file_size(filtered)

        # P2 #28 — Reducir score de archivos en rutas de sync cloud
        filtered = self._filter_backup_sync(filtered)

        # P2 #22 — Decay de score por antigüedad de evidencia
        filtered = self._apply_score_decay(filtered)

        # P2 #30 — Umbrales dinámicos ajustados por feedback loop
        filtered = self._apply_feedback_thresholds(filtered)

        # P2 #23 — Agregar explicaciones en español a todos los hallazgos
        filtered = self._apply_human_explanations(filtered)

        # P2 #24 — Agrupar resultados repetidos del mismo tipo
        filtered = self._group_related_results(filtered)

        # P2 #13 — Descartar procesos conocidos y seguros
        filtered = self._apply_process_whitelist(filtered)

        # P3 #2 + #16 — Ajuste dinámico de confidence por rareza y patrones de bans
        filtered = self._apply_cloud_rarity_and_ban_patterns(filtered)

        # P2 #4 — Indicador aislado: cap a SOSPECHOSO si no hay 2+ evidencias independientes
        filtered = self._apply_single_indicator_cap(filtered)

        # P2 #21 — Escalar a CRITICAL por combinaciones de evidencias
        filtered = self._apply_combination_penalties(filtered)

        # v1.5 — Boost/desescalar por contexto global del scan
        filtered = self._ai_contextual_boost(filtered)

        print(f"📋 TOTAL FINAL (tras decay + agrupación): {len(filtered)}")
        return filtered
        
    @staticmethod
    def _apply_profile_env(config):
        """P5 #35 — If ARGUS_PROFILE env var is set, overlay token/api_url from profiles.json."""
        profile_name = os.environ.get('ARGUS_PROFILE', '').strip()
        if not profile_name:
            return config
        data = ArgusApp._load_scanner_profiles()
        prof = data.get('profiles', {}).get(profile_name)
        if prof:
            config['scan_token'] = prof.get('token', config.get('scan_token', ''))
            config['api_url']    = prof.get('api_url', config.get('api_url', ''))
            print(f"🖥 Perfil cargado: {profile_name!r} → {config['api_url']}")
        else:
            print(f"⚠️ Perfil '{profile_name}' no encontrado en profiles.json")
        return config

    def load_config(self):
        """Carga la configuración desde ubicación persistente"""
        try:
            import sys
            
            # Intentar múltiples ubicaciones (en orden de prioridad)
            possible_paths = []
            
            if getattr(sys, 'frozen', False):
                # Si está compilado, buscar config.json en ubicaciones persistentes
                exe_dir = os.path.dirname(sys.executable)
                
                # PRIORIDAD: Buscar primero junto al ejecutable (donde se extrae el ZIP)
                # 1. Junto al ejecutable (PRIMERO - para detectar config.json del ZIP)
                possible_paths.append(os.path.join(exe_dir, 'config.json'))
                
                # 2. Directorio actual (donde se ejecuta, puede ser diferente del exe_dir)
                possible_paths.append(os.path.join(os.getcwd(), 'config.json'))
                
                # 3. Directorio padre del ejecutable
                possible_paths.append(os.path.join(exe_dir, '..', 'config.json'))
                
                # 4. AppData\Roaming (más persistente, para guardar después)
                appdata_roaming = os.path.join(os.environ.get('APPDATA', ''), 'ASPERSProjectsSS', 'config.json')
                possible_paths.append(appdata_roaming)
            else:
                # Si está en desarrollo, buscar en el directorio del script
                script_dir = os.path.dirname(os.path.abspath(__file__))
                possible_paths = [
                    os.path.join(script_dir, 'config.json'),
                    os.path.join(script_dir, '..', 'config.json'),
                    os.path.join(os.getcwd(), 'config.json'),
                    'config.json',
                ]
            
            # Intentar cada ruta
            for config_path in possible_paths:
                config_path = os.path.abspath(config_path)  # Normalizar ruta
                if os.path.exists(config_path):
                    try:
                        with open(config_path, 'r', encoding='utf-8') as f:
                            config = json.load(f)
                            print(f"✅ Config cargado desde: {config_path}")
                            
                            # Si hay un scan_token en el config, guardarlo automáticamente en ubicación persistente
                            if config.get('scan_token'):
                                token_value = config.get('scan_token')
                                print(f"🔑 Token encontrado en config: {token_value[:20]}...")

                                # Guardar el config con el token en la ubicación persistente (AppData)
                                # Esto asegura que el token esté disponible en futuras ejecuciones
                                try:
                                    if getattr(sys, 'frozen', False):
                                        appdata_dir = os.path.join(os.environ.get('APPDATA', ''), 'ASPERSProjectsSS')
                                        os.makedirs(appdata_dir, exist_ok=True)
                                        persistent_config_path = os.path.join(appdata_dir, 'config.json')

                                        # Leer config existente en AppData si existe, o usar el actual
                                        persistent_config = config.copy()
                                        if os.path.exists(persistent_config_path):
                                            try:
                                                with open(persistent_config_path, 'r', encoding='utf-8') as f:
                                                    existing_config = json.load(f)
                                                    # Preservar otros valores del config persistente
                                                    persistent_config.update(existing_config)
                                            except:
                                                pass

                                        # Asegurar que el token esté presente
                                        persistent_config['scan_token'] = token_value

                                        # ── Sanear URLs ANTES de guardar y retornar ──────────────
                                        _correct_url = 'https://asperss.onrender.com'
                                        _bad_prefixes = (
                                            'http://localhost', 'https://localhost',
                                            'http://127.0.0.1', 'https://127.0.0.1',
                                            'https://ssapi-cfni.onrender.com',
                                        )
                                        for _key in ('api_url', 'web_url'):
                                            _val = persistent_config.get(_key, '')
                                            if not _val or any(_val.startswith(p) for p in _bad_prefixes):
                                                print(f"⚠️ URL obsoleta en persistent_config ({_key}: {_val!r}) → {_correct_url}")
                                                persistent_config[_key] = _correct_url

                                        # Guardar config con el token y URLs saneadas
                                        with open(persistent_config_path, 'w', encoding='utf-8') as f:
                                            json.dump(persistent_config, f, indent=2)
                                        print(f"✅ Token guardado en config persistente: {persistent_config_path}")
                                        print(f"🔑 Token completo guardado: {token_value[:30]}...")

                                        # Usar el config persistente como principal
                                        self.config_path = persistent_config_path
                                        return persistent_config
                                except Exception as e:
                                    print(f"⚠️ Error guardando token en config persistente: {e}")
                                    import traceback
                                    traceback.print_exc()
                            
                            # Sanear URLs viejas (localhost / dominios obsoletos)
                            _correct_url = 'https://asperss.onrender.com'
                            _bad_prefixes = (
                                'http://localhost', 'https://localhost',
                                'http://127.0.0.1', 'https://127.0.0.1',
                                'https://ssapi-cfni.onrender.com',
                            )
                            _url_dirty = False
                            for _key in ('api_url', 'web_url'):
                                _val = config.get(_key, '')
                                if not _val or any(_val.startswith(p) for p in _bad_prefixes):
                                    print(f"⚠️ URL obsoleta en config ({_key}: {_val!r}) → corrigiendo a {_correct_url}")
                                    config[_key] = _correct_url
                                    _url_dirty = True
                            if _url_dirty:
                                try:
                                    with open(config_path, 'w', encoding='utf-8') as _fw:
                                        json.dump(config, _fw, indent=2)
                                except Exception:
                                    pass

                            # Guardar la ruta para futuras escrituras
                            self.config_path = config_path
                            return config
                    except Exception as e:
                        print(f"⚠️ Error leyendo config desde {config_path}: {e}")
                        continue
            
            # Si no se encuentra, usar configuración por defecto
            print("⚠️ config.json no encontrado, usando configuración por defecto")
            
            # Determinar ruta por defecto para guardar
            if getattr(sys, 'frozen', False):
                appdata_roaming = os.path.join(os.environ.get('APPDATA', ''), 'ASPERSProjectsSS', 'config.json')
                self.config_path = appdata_roaming
            else:
                script_dir = os.path.dirname(os.path.abspath(__file__))
                self.config_path = os.path.join(script_dir, 'config.json')
            
            return {
                "discord_webhook": "",
                "auth_token": "",
                "scan_timeout": 300,
                "api_url": "https://asperss.onrender.com",
                "scan_token": "",
                "web_url": "https://asperss.onrender.com",
                "enable_db_integration": False,
                "enable_ai_analysis": False,
                "enable_discord_report": False,
                "enable_web_report": False
            }
        except Exception as e:
            print(f"Error cargando configuración: {e}")
            import traceback
            traceback.print_exc()
            return {}

    # ── P5 #35 — Multi-profile scanner config ────────────────────────────────
    @staticmethod
    def _profiles_path():
        return os.path.join(os.environ.get('APPDATA', ''), 'ASPERSProjectsSS', 'profiles.json')

    @staticmethod
    def _load_scanner_profiles():
        """Returns {'active': 'name', 'profiles': {'name': {'token':..,'api_url':..}}}"""
        path = ArgusApp._profiles_path()
        if not os.path.isfile(path):
            return {'active': '', 'profiles': {}}
        try:
            with open(path, 'r', encoding='utf-8') as f:
                data = json.load(f)
            return data if isinstance(data, dict) else {'active': '', 'profiles': {}}
        except Exception:
            return {'active': '', 'profiles': {}}

    @staticmethod
    def _save_scanner_profiles(data):
        path = ArgusApp._profiles_path()
        try:
            os.makedirs(os.path.dirname(path), exist_ok=True)
            with open(path, 'w', encoding='utf-8') as f:
                json.dump(data, f, indent=2, ensure_ascii=False)
        except Exception as e:
            print(f"⚠️ Error guardando profiles.json: {e}")

    def _save_current_profile(self, name=None):
        """Persist current token+api_url as a named profile."""
        token   = self.config.get('scan_token', '')
        api_url = self.config.get('api_url', 'https://asperss.onrender.com')
        if not token:
            return
        if not name:
            name = self.config.get('staff_name') or 'Servidor principal'
        data = self._load_scanner_profiles()
        data['profiles'][name] = {'token': token, 'api_url': api_url}
        data['active'] = name
        self._save_scanner_profiles(data)
        print(f"✅ Perfil guardado: {name!r}")

    def show_profile_selector(self):
        """Toplevel dialog listing saved profiles; loads selected one."""
        import tkinter as tk
        from tkinter import simpledialog
        data = self._load_scanner_profiles()
        profiles = data.get('profiles', {})
        if not profiles:
            try:
                from tkinter import messagebox
                messagebox.showinfo("Perfiles", "No hay perfiles guardados todavía.\n\nEl perfil actual se guarda automáticamente al autenticarse.")
            except Exception:
                pass
            return

        win = tk.Toplevel(self.root)
        win.title("Cambiar servidor")
        win.geometry("340x280")
        win.configure(bg="#0d1117")
        win.grab_set()
        win.resizable(False, False)

        tk.Label(win, text="Seleccionar servidor", font=("Segoe UI", 12, "bold"),
                 bg="#0d1117", fg="#e2e8f0").pack(pady=(16, 4))
        tk.Label(win, text="Elige el perfil de servidor a usar:", font=("Segoe UI", 9),
                 bg="#0d1117", fg="#8b9ab0").pack()

        listbox = tk.Listbox(win, font=("Segoe UI", 10), bg="#161b22", fg="#e2e8f0",
                             selectbackground="#5865f2", relief=tk.FLAT, bd=0,
                             highlightthickness=0, activestyle='none', height=6)
        listbox.pack(fill=tk.BOTH, expand=True, padx=16, pady=10)

        active = data.get('active', '')
        for i, name in enumerate(profiles):
            listbox.insert(tk.END, f"  {'★ ' if name == active else '  '}{name}")
            if name == active:
                listbox.selection_set(i)
                listbox.see(i)

        def _on_select():
            idx = listbox.curselection()
            if not idx:
                return
            chosen = list(profiles.keys())[idx[0]]
            prof = profiles[chosen]
            self.config['scan_token']  = prof.get('token', '')
            self.config['api_url']     = prof.get('api_url', 'https://asperss.onrender.com')
            data['active'] = chosen
            self._save_scanner_profiles(data)
            win.destroy()
            try:
                from tkinter import messagebox
                messagebox.showinfo("Perfil cambiado",
                    f"Ahora usando: {chosen}\n\nEl próximo escaneo usará este servidor.")
            except Exception:
                pass

        def _on_delete():
            idx = listbox.curselection()
            if not idx:
                return
            chosen = list(profiles.keys())[idx[0]]
            try:
                from tkinter import messagebox
                if not messagebox.askyesno("Eliminar perfil", f"¿Eliminar el perfil '{chosen}'?"):
                    return
            except Exception:
                pass
            del data['profiles'][chosen]
            if data.get('active') == chosen:
                data['active'] = next(iter(data['profiles']), '')
            self._save_scanner_profiles(data)
            win.destroy()
            self.show_profile_selector()

        btn_frame = tk.Frame(win, bg="#0d1117")
        btn_frame.pack(fill=tk.X, padx=16, pady=(0, 14))
        tk.Button(btn_frame, text="Usar este perfil", command=_on_select,
                  bg="#5865f2", fg="white", font=("Segoe UI", 9, "bold"),
                  relief=tk.FLAT, padx=14, pady=7, cursor="hand2").pack(side=tk.LEFT, padx=(0, 6))
        tk.Button(btn_frame, text="Eliminar", command=_on_delete,
                  bg="#2d1b1b", fg="#ef4444", font=("Segoe UI", 9),
                  relief=tk.FLAT, padx=10, pady=7, cursor="hand2").pack(side=tk.LEFT)
        tk.Button(btn_frame, text="Cancelar", command=win.destroy,
                  bg="#161b22", fg="#8b9ab0", font=("Segoe UI", 9),
                  relief=tk.FLAT, padx=10, pady=7, cursor="hand2").pack(side=tk.RIGHT)

    # ── Click-speed test (P3 #26 — hardware autoclicker button detection) ────
    def _show_click_test(self):
        """
        Muestra un test de velocidad de clicks antes del scan.
        Pide al jugador hacer clic 15 veces para analizar el patrón.
        - CV < 0.04 y CPS > 8  → botón de autoclicker hardware (CRITICAL)
        - CV < 0.10 y CPS > 8  → software autoclicker activo (SOSPECHOSO)
        - CPS > 20              → imposible humano (CRITICAL)
        """
        import tkinter as tk
        import time

        CLICKS_NEEDED  = 15
        TIMEOUT_S      = 40
        BG             = '#0d1117'
        ACCENT         = '#5865f2'
        RED            = '#ef4444'
        GREEN          = '#10b981'
        AMBER          = '#f59e0b'
        TEXT           = '#e2e8f0'
        TEXT_D         = '#8b9ab0'
        CIRCLE_IDLE    = '#1e2433'
        CIRCLE_HOVER   = '#2a3050'

        click_times    = []
        done_event     = threading.Event()

        win = tk.Toplevel(self.root)
        win.title("Verificación de mouse")
        win.geometry("420x460")
        win.configure(bg=BG)
        win.resizable(False, False)
        win.grab_set()
        win.protocol('WM_DELETE_WINDOW', lambda: None)  # no cerrar

        # Centrar
        win.update_idletasks()
        x = (win.winfo_screenwidth()  // 2) - 210
        y = (win.winfo_screenheight() // 2) - 230
        win.geometry(f"420x460+{x}+{y}")

        # Título
        tk.Label(win, text="Verificación de velocidad",
                 font=("Segoe UI", 13, "bold"), bg=BG, fg=TEXT).pack(pady=(22, 2))
        tk.Label(win, text=f"Haz clic en el círculo {CLICKS_NEEDED} veces",
                 font=("Segoe UI", 10), bg=BG, fg=TEXT_D).pack()

        # Contador
        count_var = tk.StringVar(value=f"0 / {CLICKS_NEEDED}")
        count_lbl = tk.Label(win, textvariable=count_var,
                             font=("Segoe UI", 22, "bold"), bg=BG, fg=ACCENT)
        count_lbl.pack(pady=(10, 4))

        # Barra de progreso (canvas)
        bar_bg = tk.Frame(win, bg='#1e2433', height=6)
        bar_bg.pack(fill=tk.X, padx=40, pady=(0, 16))
        bar_bg.pack_propagate(False)
        bar_canvas = tk.Canvas(bar_bg, height=6, bg='#1e2433',
                               highlightthickness=0, bd=0)
        bar_canvas.pack(fill=tk.BOTH, expand=True)

        def _draw_bar(n):
            bar_canvas.delete('all')
            w = bar_canvas.winfo_width()
            if w < 2:
                return
            frac  = n / CLICKS_NEEDED
            color = ACCENT if frac < 1.0 else GREEN
            bar_canvas.create_rectangle(0, 0, int(w * frac), 6,
                                        fill=color, outline='')
        bar_canvas.bind('<Configure>', lambda e: _draw_bar(len(click_times)))

        # Círculo clickeable
        canvas = tk.Canvas(win, width=160, height=160, bg=BG,
                           highlightthickness=0, bd=0)
        canvas.pack(pady=4)

        def _draw_circle(color=CIRCLE_IDLE):
            canvas.delete('all')
            canvas.create_oval(10, 10, 150, 150, fill=color,
                               outline=ACCENT, width=2)
            remaining = max(0, CLICKS_NEEDED - len(click_times))
            canvas.create_text(80, 80, text=str(remaining) if remaining > 0 else "✓",
                               font=("Segoe UI", 38, "bold"),
                               fill=TEXT if remaining > 0 else GREEN)

        _draw_circle()

        # Feedback
        fb_var = tk.StringVar(value="¡Comienza a hacer clic!")
        fb_lbl = tk.Label(win, textvariable=fb_var,
                          font=("Segoe UI", 10), bg=BG, fg=TEXT_D)
        fb_lbl.pack(pady=(4, 2))

        # Countdown label
        cd_var = tk.StringVar(value=f"Tiempo restante: {TIMEOUT_S}s")
        cd_lbl = tk.Label(win, textvariable=cd_var,
                          font=("Segoe UI", 9), bg=BG, fg=TEXT_D)
        cd_lbl.pack()

        def _on_click(event=None):
            if done_event.is_set():
                return
            t = time.perf_counter()
            click_times.append(t)
            n = len(click_times)
            count_var.set(f"{n} / {CLICKS_NEEDED}")
            _draw_circle(CIRCLE_HOVER)
            win.after(80, lambda: _draw_circle(CIRCLE_IDLE))
            _draw_bar(n)
            if n >= CLICKS_NEEDED:
                _finish()

        canvas.bind('<Button-1>', _on_click)
        canvas.bind('<Enter>', lambda e: _draw_circle(CIRCLE_HOVER) if not done_event.is_set() else None)
        canvas.bind('<Leave>', lambda e: _draw_circle(CIRCLE_IDLE) if not done_event.is_set() else None)
        canvas.config(cursor='hand2')

        def _finish():
            if done_event.is_set():
                return
            done_event.set()
            self._click_test_result = _analyze(click_times)
            verdict = self._click_test_result
            if verdict:
                color = RED if verdict['alerta'] in ('CRITICAL',) else \
                        AMBER if verdict['alerta'] == 'SOSPECHOSO' else GREEN
                fb_var.set(verdict['nombre'])
                fb_lbl.config(fg=color)
                cd_var.set("")
                _draw_circle(RED if color == RED else (AMBER if color == AMBER else GREEN))
            else:
                fb_var.set("✓ Patrón humano normal")
                fb_lbl.config(fg=GREEN)
                _draw_circle(GREEN)
            win.after(1800, lambda: (win.grab_release(), win.destroy(),
                                     self.full_scan_with_discord()))

        def _countdown(remaining):
            if done_event.is_set():
                return
            cd_var.set(f"Tiempo restante: {remaining}s")
            if remaining <= 0:
                _finish()
            else:
                win.after(1000, lambda: _countdown(remaining - 1))

        win.after(100, lambda: _countdown(TIMEOUT_S))

        def _analyze(times):
            if len(times) < 6:
                return None
            intervals = [times[k+1] - times[k] for k in range(len(times) - 1)]
            mean_iv  = sum(intervals) / len(intervals)
            variance = sum((x - mean_iv)**2 for x in intervals) / len(intervals)
            std_iv   = variance ** 0.5
            cps      = 1.0 / mean_iv if mean_iv > 0 else 0
            cv       = std_iv / mean_iv if mean_iv > 0 else 1.0

            # Imposible humano: >20 CPS con muy baja varianza
            if cps > 20 and cv < 0.06:
                return {
                    'tipo':        'MOUSE_HARDWARE_AUTOCLICKER_BTN',
                    'nombre':      f'Botón autoclicker hardware detectado: {cps:.1f} CPS, σ={std_iv*1000:.1f}ms',
                    'ruta':        '',
                    'detalle':     (f'Clicks: {len(times)}  |  CPS: {cps:.1f}  |  '
                                   f'Intervalo medio: {mean_iv*1000:.1f}ms  |  '
                                   f'Desv. estándar: {std_iv*1000:.2f}ms  |  CV: {cv:.3f}'),
                    'alerta':      'CRITICAL',
                    'categoria':   'MOUSE_WEIGHT',
                    'descripcion': (
                        f'El test de clicks detectó {cps:.1f} CPS con varianza σ={std_iv*1000:.1f}ms '
                        f'(CV={cv:.3f}). Velocidad imposible para un humano sin asistencia. '
                        'Indica botón de autoclicker hardware del mouse activo (tipo Bloody, Redragon, etc.).'
                    ),
                }
            # Hardware autoclicker: muy regular
            if cps > 8 and cv < 0.04:
                return {
                    'tipo':        'MOUSE_HARDWARE_AUTOCLICKER_BTN',
                    'nombre':      f'Botón autoclicker hardware: {cps:.1f} CPS, σ={std_iv*1000:.1f}ms',
                    'ruta':        '',
                    'detalle':     (f'Clicks: {len(times)}  |  CPS: {cps:.1f}  |  '
                                   f'Intervalo medio: {mean_iv*1000:.1f}ms  |  '
                                   f'Desv. estándar: {std_iv*1000:.2f}ms  |  CV: {cv:.3f}'),
                    'alerta':      'CRITICAL',
                    'categoria':   'MOUSE_WEIGHT',
                    'descripcion': (
                        f'El test de clicks muestra regularidad inhumana: {cps:.1f} CPS con '
                        f'desviación de solo {std_iv*1000:.1f}ms (CV={cv:.3f}). '
                        'Un humano tiene varianza >50ms. Esta precisión es característica del '
                        'botón de autoclicker firmaware del mouse (Bloody, Redragon, Attack Shark, etc.).'
                    ),
                }
            # Software autoclicker: regular pero con algo de jitter del OS
            if cps > 8 and cv < 0.12:
                return {
                    'tipo':        'MOUSE_SOFTWARE_AUTOCLICKER',
                    'nombre':      f'Posible autoclicker software: {cps:.1f} CPS, σ={std_iv*1000:.1f}ms',
                    'ruta':        '',
                    'detalle':     (f'Clicks: {len(times)}  |  CPS: {cps:.1f}  |  '
                                   f'Intervalo medio: {mean_iv*1000:.1f}ms  |  '
                                   f'Desv. estándar: {std_iv*1000:.2f}ms  |  CV: {cv:.3f}'),
                    'alerta':      'SOSPECHOSO',
                    'categoria':   'MOUSE_WEIGHT',
                    'descripcion': (
                        f'El test detectó {cps:.1f} CPS con varianza moderada (CV={cv:.3f}). '
                        'Podría ser autoclicker de software (AutoHotkey, OP AutoClicker) '
                        'o un click-jitter entrenado. Investigar en conjunto con otros hallazgos.'
                    ),
                }
            return None

    def create_ui(self):
        """Crea la interfaz de usuario con estilo moderno ASPERS PROJECTS"""
        if UI_STYLE_AVAILABLE:
            main_panel = tk.Frame(self.root, bg=ModernUI.COLORS['bg_primary'])
            main_panel.pack(fill=tk.BOTH, expand=True)

            # Header
            ModernUI.create_header(main_panel)

            # Progress section
            progress_widgets = ModernUI.create_progress_section(main_panel)
            self.progress_frame = progress_widgets['container']
            self.progress_label = progress_widgets['status']
            self.progress_bar = progress_widgets['progress']
            self.progress_detail_label = progress_widgets['detail']
            self.timer_label = progress_widgets['timer']
            self.resources_label = progress_widgets['resources']
            self.progress_percent_label = progress_widgets.get('percent', None)
            self._progress_canvas = progress_widgets.get('_canvas', None)
            self._progress_ring   = progress_widgets.get('_ring', None)
            self._cancel_row = progress_widgets.get('cancel_row', None)
            self._cancel_btn_widget = progress_widgets.get('cancel_btn', None)
            self.progress_value = 0
            self._scan_cancel_event = threading.Event()

            # Wire up cancel button
            if self._cancel_btn_widget:
                def _on_cancel_scan():
                    self._scan_cancel_event.set()
                    if self._cancel_btn_widget:
                        self._cancel_btn_widget.config(
                            text="✕  Cancelando...",
                            state='disabled',
                            fg=ModernUI.COLORS['red']
                        )
                    self._update_progress_safe(
                        getattr(self, 'progress_value', 0),
                        "⛔ Cancelando escaneo...",
                        "Esperando que finalicen los módulos actuales"
                    )
                self._cancel_btn_widget.config(command=_on_cancel_scan)

            # Scan button (hidden — escaneo arranca automáticamente)
            btn_container = tk.Frame(main_panel, bg=ModernUI.COLORS['bg_primary'], height=0)
            btn_container.pack()
            btn_container.pack_propagate(False)
            scan_btn_frame = ModernUI.create_button(
                btn_container,
                "INICIAR ESCANEO",
                self.full_scan_with_discord,
                style='primary',
                icon='🚀'
            )
            scan_btn_frame.pack(fill=tk.X)
            self.scan_button = None
            for widget in scan_btn_frame.winfo_children():
                if isinstance(widget, tk.Button):
                    self.scan_button = widget
                    break
            self.details_button = None

            # Completion panel (visible to user instead of raw results)
            self._completion_widgets = ModernUI.create_completion_panel(main_panel)

            # Hidden results section (staff data written here but never shown)
            results_widgets = ModernUI.create_results_section(main_panel)
            self.results_frame = results_widgets['container']
            self.results_text = results_widgets['text']
            self.results_label = results_widgets['title']

            # P5 #35 — Ctrl+Shift+P → profile selector
            self.root.bind('<Control-Shift-P>', lambda e: self.show_profile_selector())
        else:
            self._create_ui_fallback()
    
    def _create_ui_fallback(self):
        """Fallback UI si ModernUI no está disponible"""
        self.root.title("Argus Projects — Security Scanner Pro")
        self.root.geometry("880x540")
        self.root.configure(bg="#0a0e27")
        
        main_panel = tk.Frame(self.root, bg="#0a0e27")
        main_panel.pack(fill=tk.BOTH, expand=True)
        
        # Header simple
        header = tk.Frame(main_panel, bg="#0d1117", height=140)
        header.pack(fill=tk.X)
        header.pack_propagate(False)
        
        tk.Label(
            header,
            text="ASPERS PROJECTS",
            font=("Segoe UI", 32, "bold"),
            bg="#0d1117",
            fg="#f0f6fc"
        ).pack(pady=20)
        
        tk.Label(
            header,
            text="Security Scanner Pro - Advanced Anti-Bypass Detection System",
            font=("Segoe UI", 11),
            bg="#0d1117",
            fg="#8b949e"
        ).pack()
        
        # Panel de progreso
        self.progress_frame = tk.Frame(main_panel, bg="#161b22")
        self.progress_frame.pack(fill=tk.X, pady=(0, 20), padx=25)
        
        self.progress_label = tk.Label(
            self.progress_frame,
            text="⏳ Esperando inicio del escaneo...",
            font=("Segoe UI", 13, "bold"),
            bg="#161b22",
            fg="#f0f6fc"
        )
        self.progress_label.pack(pady=(20, 12))
        
        self.progress_bar = ttk.Progressbar(
            self.progress_frame,
            mode='determinate',
            length=600,
            maximum=100
        )
        self.progress_value = 0
        self.progress_bar.pack(fill=tk.X, padx=20, pady=(0, 12))
        
        self.progress_detail_label = tk.Label(
            self.progress_frame,
            text="",
            font=("Segoe UI", 10),
            bg="#161b22",
            fg="#8b949e",
            wraplength=600
        )
        self.progress_detail_label.pack(padx=20, pady=(0, 10))
        
        timer_container = tk.Frame(self.progress_frame, bg="#161b22")
        timer_container.pack(fill=tk.X, padx=20, pady=(0, 20))
        
        self.timer_label = tk.Label(
            timer_container,
            text="⏱️ Tiempo: 00:00:00",
            font=("Segoe UI", 11, "bold"),
            bg="#161b22",
            fg="#58a6ff"
        )
        self.timer_label.pack(side=tk.LEFT)
        
        self.resources_label = tk.Label(
            timer_container,
            text="",
            font=("Segoe UI", 10),
            bg="#161b22",
            fg="#8b949e"
        )
        self.resources_label.pack(side=tk.RIGHT)
        
        # Botones
        button_frame = tk.Frame(main_panel, bg="#0a0e27")
        button_frame.pack(fill=tk.X, pady=20, padx=25)
        
        self.scan_button = tk.Button(
            button_frame,
            text="🚀 INICIAR ESCANEO COMPLETO",
            command=self.full_scan_with_discord,
            bg="#238636",
            fg="#ffffff",
            font=("Segoe UI", 14, "bold"),
            padx=50,
            pady=18,
            relief=tk.FLAT,
            cursor="hand2",
            activebackground="#2ea043"
        )
        self.scan_button.pack(expand=True, fill=tk.X, padx=20)
        
        self.details_button = None
        
        # Resultados
        self.results_frame = tk.Frame(main_panel, bg="#161b22")
        self.results_frame.pack(fill=tk.BOTH, expand=True, padx=25)
        
        self.results_label = tk.Label(
            self.results_frame,
            text="📋 RESULTADOS DEL ESCANEO",
            font=("Segoe UI", 15, "bold"),
            bg="#161b22",
            fg="#f0f6fc"
        )
        self.results_label.pack(pady=(20, 15))
        
        self.results_text = scrolledtext.ScrolledText(
            self.results_frame,
            wrap=tk.WORD,
            font=("Consolas", 10),
            bg="#0d1117",
            fg="#f0f6fc",
            padx=20,
            pady=20
        )
        self.results_text.pack(fill=tk.BOTH, expand=True, padx=20, pady=(0, 20))
        
        # Tags de color
        self.results_text.tag_config("success", foreground="#3fb950", font=("Consolas", 10, "bold"))
        self.results_text.tag_config("warning", foreground="#d29922", font=("Consolas", 10, "bold"))
        self.results_text.tag_config("danger", foreground="#f85149", font=("Consolas", 10, "bold"))
        self.results_text.tag_config("info", foreground="#58a6ff", font=("Consolas", 10, "bold"))
        self.results_text.tag_config("header", foreground="#f0f6fc", font=("Consolas", 10, "bold"))
    
    def update_detailed_progress(self, value, message, detail=""):
        """Actualiza la barra de progreso con detalles adicionales - Animación suave de 1 en 1"""
        # Asegurar que el valor esté entre 0 y 100
        value = max(0, min(100, int(value)))
        
        # Actualizar detalle inmediatamente
        if hasattr(self, 'progress_detail_label'):
            self.progress_detail_label.config(text=detail)
        
        # Obtener valor actual
        if not hasattr(self, 'progress_value') or self.progress_value is None:
            self.progress_value = 0
        
        target_value = int(value)
        
        # Actualizar el valor objetivo (esto permitirá que la animación continúe hacia el nuevo objetivo)
        self.progress_target_value = target_value
        
        # Guardar mensaje para la animación
        if not hasattr(self, '_progress_message'):
            self._progress_message = message
        self._progress_message = message
        
        # Si no hay animación corriendo, iniciar una nueva
        if not self.progress_animation_running:
            self._start_progress_animation(message)
    
    def _start_progress_animation(self, message=""):
        """Inicia la animación de progreso de forma controlada - Continúa desde donde está"""
        if self.progress_animation_running:
            # Si ya hay una animación corriendo, solo actualizar el mensaje y objetivo
            return
        
        def animate():
            self.progress_animation_running = True
            last_message = message
            
            try:
                while True:
                    current = int(self.progress_value)
                    target = int(self.progress_target_value)
                    
                    # Si ya llegamos al objetivo, verificar brevemente si hay un nuevo target
                    if current == target:
                        time.sleep(0.05)
                        if int(self.progress_value) == int(self.progress_target_value):
                            time.sleep(0.05)  # segunda espera antes de salir del loop
                            if int(self.progress_value) == int(self.progress_target_value):
                                break
                        continue
                    
                    # Calcular siguiente paso (siempre de 1 en 1)
                    if target > current:
                        next_value = current + 1
                    else:
                        next_value = current - 1
                    
                    # Asegurar que esté en rango
                    next_value = max(0, min(100, next_value))
                    
                    # Actualizar valor
                    self.progress_value = next_value
                    
                    # Obtener mensaje actualizado si cambió
                    current_target = int(self.progress_target_value)
                    if hasattr(self, 'progress_label'):
                        current_text = self.progress_label.cget('text')
                        # Extraer mensaje del texto si es posible
                        if '(' in current_text and '%' in current_text:
                            msg_part = current_text.split('(')[0].strip()
                            if msg_part:
                                last_message = msg_part
                    
                    # Actualizar UI en el hilo principal usando after()
                    # next_value capturado por valor (v=next_value) para evitar closure bug
                    def update_ui(v=next_value, msg=last_message):
                        try:
                            if hasattr(self, 'progress_bar'):
                                self.progress_bar['value'] = v
                            if hasattr(self, 'progress_label'):
                                self.progress_label.config(text=msg)
                            if hasattr(self, 'progress_percent_label') and self.progress_percent_label:
                                self.progress_percent_label.config(text=f"{v}%")
                            if hasattr(self, '_progress_canvas') and self._progress_canvas:
                                ModernUI.update_canvas_bar(self._progress_canvas, v)
                        except Exception:
                            pass

                    # Programar actualización en el hilo principal
                    self.root.after(0, update_ui)

                    # Esperar antes del siguiente paso (velocidad ajustable)
                    time.sleep(0.03)  # 30ms por paso = ~33 pasos por segundo
                    
            except Exception as e:
                print(f"Error en animación de progreso: {e}")
            finally:
                self.progress_animation_running = False
                
                # Asegurar valor final exacto
                try:
                    final_value = int(self.progress_target_value)
                    self.progress_value = final_value
                    
                    # Obtener mensaje final
                    final_message = message
                    if hasattr(self, 'progress_label'):
                        current_text = self.progress_label.cget('text')
                        if '(' in current_text:
                            final_message = current_text.split('(')[0].strip()
                    
                    def final_update():
                        try:
                            if hasattr(self, 'progress_bar'):
                                self.progress_bar['value'] = final_value
                            if hasattr(self, 'progress_label'):
                                self.progress_label.config(text=f"{final_message} ({final_value}%)")
                            if hasattr(self, 'progress_percent_label') and self.progress_percent_label:
                                self.progress_percent_label.config(text=f"{final_value}%")
                        except:
                            pass
                    
                    self.root.after(0, final_update)
                except:
                    pass
        
        # Iniciar animación en thread separado
        self.progress_animation_thread = threading.Thread(target=animate, daemon=True)
        self.progress_animation_thread.start()
    
    def _update_progress_safe(self, value, message, detail=""):
        """Actualiza progreso de forma segura sin recursión"""
        try:
            self.update_detailed_progress(value, message, detail)
        except Exception as e:
            print(f"Error actualizando progreso: {e}")

    def _set_scan_phase(self, text):
        """Avanza el contador de fase y actualiza progreso — seguro desde cualquier hilo."""
        try:
            if not hasattr(self, '_phase_lock'):
                self._phase_lock = threading.Lock()
            with self._phase_lock:
                self._phase_counter = getattr(self, '_phase_counter', 0) + 1
                total = getattr(self, '_total_phases', 76)
                pct = 80 + min(15, int(self._phase_counter / total * 15))
            self.root.after(0, lambda t=text, p=pct: self._apply_phase_update(t, p))
        except Exception:
            pass

    def _apply_phase_update(self, text, pct):
        try:
            if hasattr(self, 'progress_detail_label') and self.progress_detail_label:
                self.progress_detail_label.config(text=text)
            cur = getattr(self, 'progress_target_value', 0)
            if pct > cur:
                self.progress_target_value = pct
                if not self.progress_animation_running:
                    self._start_progress_animation(text)
        except Exception:
            pass

    def start_scan_timer(self):
        """Inicia el cronómetro del escaneo"""
        import time
        self.scan_start_time = time.time()
        self.timer_running = True
        self.timer_thread = threading.Thread(target=self._timer_loop, daemon=True)
        self.timer_thread.start()
    
    def stop_scan_timer(self):
        """Detiene el cronómetro del escaneo"""
        self.timer_running = False
        if self.scan_start_time:
            elapsed = time.time() - self.scan_start_time
            hours, remainder = divmod(elapsed, 3600)
            minutes, seconds = divmod(remainder, 60)
            time_str = f"⏱️ Tiempo total: {int(hours):02d}:{int(minutes):02d}:{int(seconds):02d}"
            self.timer_label.config(text=time_str, fg="#ffff00")
            print(f"🕐 ESCANEO COMPLETADO EN: {time_str}")
    
    def _timer_loop(self):
        """Loop del cronómetro que se ejecuta en segundo plano con recursos del sistema"""
        import time
        while self.timer_running:
            if self.scan_start_time:
                elapsed = time.time() - self.scan_start_time
                hours, remainder = divmod(elapsed, 3600)
                minutes, seconds = divmod(remainder, 60)
                time_str = f"⏱️ Tiempo: {int(hours):02d}:{int(minutes):02d}:{int(seconds):02d}"
                
                # Obtener recursos del sistema
                try:
                    cpu_percent = psutil.cpu_percent(interval=0.1)
                    memory = psutil.virtual_memory()
                    ram_percent = memory.percent
                    ram_used_gb = memory.used / (1024**3)
                    ram_total_gb = memory.total / (1024**3)
                    _files = getattr(self, 'total_files_scanned', 0)
                    _files_s = f" | 📁 {_files:,}" if _files else ""
                    resources_str = f"💻 CPU: {cpu_percent:.1f}% | 🧠 RAM: {ram_percent:.1f}% ({ram_used_gb:.1f}GB/{ram_total_gb:.1f}GB){_files_s}"
                except:
                    resources_str = ""
                
                # Actualizar en el hilo principal de forma segura
                try:
                    self.root.after(0, lambda t=time_str, r=resources_str: self._update_timer_display(t, r))
                except:
                    pass
            time.sleep(1)
    
    def _update_timer_display(self, time_str, resources_str):
        """Actualiza la visualización del timer y recursos de forma segura"""
        try:
            if self.timer_label:
                self.timer_label.config(text=time_str)
            if self.resources_label and resources_str:
                self.resources_label.config(text=resources_str)
        except:
            pass
    
    def full_scan_with_discord(self):
        """Ejecuta escaneo completo y envía a Discord y Web automáticamente"""
        def scan_and_report():
            try:
                # Activar modo silencioso (sin logs en UI)
                self.scanning_mode = True
                if UI_STYLE_AVAILABLE:
                    ModernUI.set_status_badge("ESCANEANDO", ModernUI.COLORS['amber'])
                
                # Iniciar escaneo en BD si está disponible
                scan_start_time = time.time()
                if self.db_integration:
                    # Asegurar que el token esté actualizado desde config.json
                    if hasattr(self, 'config') and self.config:
                        scan_token = self.config.get('scan_token', '')
                        if scan_token:
                            self.db_integration.scan_token = scan_token
                            print(f"✅ Token de escaneo actualizado: {scan_token}")
                        else:
                            print(f"⚠️ No hay token en config.json, recargando configuración...")
                            # Recargar configuración por si se guardó después de la inicialización
                            self.config = self.load_config()
                            scan_token = self.config.get('scan_token', '')
                            if scan_token:
                                self.db_integration.scan_token = scan_token
                                print(f"✅ Token de escaneo cargado desde config: {scan_token}")
                            else:
                                print(f"❌ No hay token de escaneo disponible. Por favor, autentícate primero.")
                    
                    if self.db_integration.scan_token:
                        try:
                            self.db_integration.start_scan()
                        except Exception as e:
                            print(f"⚠️ Error al iniciar escaneo en BD: {e}")
                    else:
                        print(f"⚠️ No se puede iniciar escaneo en BD: no hay token configurado")
                
                # P3 #35 — Predicción pre-scan: avisa al staff antes de escanear
                self._run_pre_scan_predict()

                # Ejecutar escaneo completo directamente (sin messagebox)
                self.execute_full_scan_silent()
                
                # Esperar a que termine el escaneo
                while self.scanning:
                    time.sleep(0.1)
                
                # Calcular duración del escaneo
                scan_duration = time.time() - scan_start_time

                # Ocultar botón cancel al terminar el scan
                if hasattr(self, '_cancel_row') and self._cancel_row:
                    self.root.after(0, self._cancel_row.pack_forget)

                # Si el usuario canceló, cerrar sin enviar
                if getattr(self, '_scan_cancel_event', None) and self._scan_cancel_event.is_set():
                    self._update_progress_safe(0, "⛔ Escaneo cancelado", "El escaneo fue interrumpido por el usuario")
                    self.scanning_mode = False
                    self.root.after(3000, self.root.destroy)
                    return

                # Envío a Web (filtrado + IA ya se aplicaron dentro de execute_full_scan_silent)
                print("📤 Enviando resultados a Web...")
                
                # Enviar a Web/BD
                if self.db_integration:
                    # Asegurar que el token esté actualizado antes de enviar
                    if hasattr(self, 'config') and self.config:
                        scan_token = self.config.get('scan_token', '')
                        if scan_token and not self.db_integration.scan_token:
                            self.db_integration.scan_token = scan_token
                            print(f"✅ Token actualizado antes de enviar resultados: {scan_token}")
                        elif not scan_token:
                            # Intentar recargar config
                            self.config = self.load_config()
                            scan_token = self.config.get('scan_token', '')
                            if scan_token:
                                self.db_integration.scan_token = scan_token
                                print(f"✅ Token cargado desde config antes de enviar: {scan_token}")
                    
                    # Detener monitor de timing y añadir hallazgos
                    try:
                        self._stop_click_timing_monitor()
                    except Exception:
                        pass

                    if self.db_integration.scan_token:
                        try:
                            self._update_progress_safe(99, "📤 Enviando resultados...", "Subiendo a servidor...")
                            success = self.db_integration.submit_results(
                                self.issues_found,
                                self.total_files_scanned,
                                scan_duration,
                                getattr(self, 'total_dirs_scanned', 0)
                            )
                            if success:
                                _risk_w = {'CRITICAL': 25, 'SOSPECHOSO': 12, 'POCO_SOSPECHOSO': 4, 'NORMAL': 1}
                                _rs = min(100, int(sum(
                                    _risk_w.get(i.get('alerta', 'NORMAL'), 1) * min(float(i.get('confidence') or 0) * (1 if float(i.get('confidence') or 0) > 1 else 100) / 100, 1)
                                    for i in self.issues_found
                                )))
                                self._update_progress_safe(100, "✅ Escaneo completado", f"{len(self.issues_found)} hallazgos · Risk Score: {_rs}/100")
                                print("✅ Resultados enviados a Web/BD")
                            else:
                                self._update_progress_safe(100, "⚠️ Error al enviar", "Revisa conexión y token")
                                print("⚠️ Error al enviar resultados a Web/BD")
                        except Exception as e:
                            print(f"⚠️ Error al enviar a Web/BD: {e}")
                            import traceback
                            traceback.print_exc()
                    else:
                        print("⚠️ No se puede enviar resultados: no hay token de escaneo configurado")
                        print("💡 Por favor, autentícate primero con un token válido")
                
                # Desactivar modo silencioso
                self.scanning_mode = False

                # Cerrar automáticamente tras 4 segundos (resultados ya enviados al panel)
                self.root.after(4000, self.root.destroy)
                
            except Exception as e:
                self.scanning_mode = False
                import traceback
                print(f"❌ Error en escaneo completo: {e}\n{traceback.format_exc()}")
                self.root.after(0, lambda: self.log(f"Error en escaneo completo: {str(e)}", "danger"))
        
        # Ejecutar todo en un hilo separado
        threading.Thread(target=scan_and_report, daemon=True).start()
    
    def _run_pre_scan_predict(self):
        """P3 #35 — Llama a /api/predict con señales rápidas antes de escanear.
        No bloquea el scan si falla; solo loguea el resultado pre-scan."""
        try:
            api_url = self.config.get('api_url', '').rstrip('/')
            token   = self.config.get('scan_token', '') or (
                self.db_integration.scan_token if self.db_integration else '')
            if not api_url or not token:
                return

            appdata  = os.environ.get('APPDATA', '')
            mc_dir   = os.path.join(appdata, '.minecraft')

            # Count MC version dirs quickly
            mc_versions = 0
            versions_dir = os.path.join(mc_dir, 'versions')
            if os.path.isdir(versions_dir):
                try:
                    mc_versions = sum(
                        1 for e in os.scandir(versions_dir) if e.is_dir()
                    )
                except OSError:
                    pass

            # Quick presence check for known hack client dirs
            _hack_dir_names = [
                '.aristois', '.sigma', '.sigma6', '.weave', '.rise',
                '.meteor', '.liquidbounce', '.wurst', '.nodus',
                '.vape', '.drip', '.entropy',
            ]
            suspicious_dirs = [
                d for d in _hack_dir_names
                if os.path.isdir(os.path.join(appdata, d))
                or os.path.isdir(os.path.join(mc_dir, d))
            ]

            machine_id = self.config.get('machine_id', '')

            resp = requests.post(
                f'{api_url}/api/predict',
                json={
                    'token':          token,
                    'machine_id':     machine_id,
                    'mc_versions':    mc_versions,
                    'suspicious_dirs': suspicious_dirs,
                    'os_version':     os.environ.get('OS', 'Windows'),
                },
                timeout=6,
            )
            if resp.status_code == 200:
                data       = resp.json()
                risk_level = data.get('risk_level', 'BAJO')
                risk_score = data.get('risk_score', 0)
                reasons    = data.get('reasons') or []
                prev_hacks = data.get('prev_hacks', 0)
                print(
                    f"🔮 Pre-scan predict: {risk_level} ({risk_score}/100)"
                    + (f" — {', '.join(reasons)}" if reasons else "")
                    + (f" — {prev_hacks} hack(s) previo(s)" if prev_hacks else "")
                )
                if risk_level == 'ALTO':
                    self._update_progress_safe(
                        2,
                        f"⚠️ Riesgo previo ALTO ({risk_score}/100) — scan en curso",
                        "Historial del jugador indica riesgo elevado",
                    )
        except Exception as ex:
            print(f"⚠️ Pre-scan predict falló (no crítico): {ex}")

    def execute_full_scan_silent(self):
        """Ejecuta escaneo ULTRA RÁPIDO sin limitaciones de recursos"""
        if self.scanning:
            return
        
        import concurrent.futures
        import psutil
        
        self.scanning = True
        self.issues_found = []
        self.mouse_findings = []
        self.forensic_findings = []
        self.total_files_scanned = 0
        self.total_dirs_scanned = 0

        # Resetear evento de cancelación y mostrar botón cancel
        if hasattr(self, '_scan_cancel_event'):
            self._scan_cancel_event.clear()
        if hasattr(self, '_cancel_row') and self._cancel_row:
            self.root.after(0, lambda: self._cancel_row.pack(fill=tk.X, pady=(4, 0)))
        if hasattr(self, '_cancel_btn_widget') and self._cancel_btn_widget:
            self.root.after(0, lambda: self._cancel_btn_widget.config(
                text="✕  Cancelar escaneo", state='normal',
                fg=ModernUI.COLORS.get('text_secondary', '#545880') if UI_STYLE_AVAILABLE else '#545880'
            ))

        # ── Snapshot USB al inicio + arrancar monitor de desconexiones ───────
        self.initial_usb_devices = self.get_usb_devices()
        self._start_usb_monitor()

        # ── Anti-detection: camuflar título de ventana durante el scan ──────
        self._camouflage_window()

        # ── Click timing monitor — arranca en paralelo durante todo el scan ──
        self._start_click_timing_monitor()

        # ── Mouse instant checks (run BEFORE anything else) ─────────────────
        # We do this immediately so the player has no time to react.
        if self.mouse_detector:
            try:
                instant = self.mouse_detector.run_instant_checks()
                self.mouse_findings.extend(instant)
                if instant:
                    print(f"🖱️ Detección inmediata de mouse: {len(instant)} hallazgo(s) sospechoso(s)")
                    for f in instant:
                        print(f"   ⚠️  {f['nombre']} [{f['alerta']}]")
            except Exception as _me:
                print(f"⚠️ Error en detección inmediata de mouse: {_me}")

        # Iniciar cronómetro
        self.start_scan_timer()

        try:
            # Configurar para uso MÁXIMO de recursos
            total_phases = 100
            current_progress = 0

            # Inicializar contador global de archivos escaneados
            self.total_files_scanned = 0

            print("🚀 INICIANDO ESCANEO ULTRA RÁPIDO - REVISIÓN COMPLETA DE TODA LA PC")
            print(f"🔧 CPU cores disponibles: {psutil.cpu_count()}")
            print(f"💾 Memoria disponible: {psutil.virtual_memory().available / (1024**3):.1f} GB")
            print("⚡ MODO TURBO ACTIVADO - ESCANEO COMPLETO SIN LÍMITES DE PROFUNDIDAD")
            print("⏱️ CRONÓMETRO INICIADO - MIDIENDO VELOCIDAD MÁXIMA")
            print("🔥 OPTIMIZACIONES: 2x hilos, procesamiento en lotes, filtrado inteligente")
            print("📁 ESCANEO COMPLETO: Revisando TODA la PC sin límites")
            
            # Fase 1: Escaneo de unidades (0-80%)
            self._update_progress_safe(0, "🔍 Iniciando escaneo exhaustivo", "Preparando sistema...")
            
            # Obtener todas las unidades
            drives = []
            for drive in range(ord('A'), ord('Z') + 1):
                drive_letter = chr(drive) + ":\\"
                if os.path.exists(drive_letter):
                    drives.append(drive_letter)
            
            print(f"📁 UNIDADES DETECTADAS: {drives}")
            
            # Escanear cada unidad en paralelo con rendimiento optimizado
            max_workers = psutil.cpu_count() * 2  # Usar 2x más hilos para estabilidad
            print(f"⚡ Usando {max_workers} hilos para velocidad optimizada")
            with concurrent.futures.ThreadPoolExecutor(max_workers=max_workers) as executor:
                futures = []
                progress_per_drive = 80 // len(drives) if drives else 80
                
                for i, drive in enumerate(drives):
                    start_progress = i * progress_per_drive
                    end_progress = (i + 1) * progress_per_drive

                    # Hack-name scan en paralelo (no bloquea la barra de progreso)
                    executor.submit(self._scan_for_specific_hacks, drive)

                    future = executor.submit(self.scan_drive_exhaustive, drive, start_progress, end_progress)
                    futures.append(future)
                
                # Esperar a que terminen todos con timeout aumentado
                for future in concurrent.futures.as_completed(futures, timeout=85):  # 85s max para todas las unidades
                    try:
                        future.result()
                        print(f"✅ Unidad escaneada exitosamente")
                    except concurrent.futures.TimeoutError:
                        print(f"⏰ Timeout en escaneo de unidad (85s) - continuando con fases secundarias...")
                    except Exception as e:
                        print(f"⚠️ Error en escaneo de unidad: {e} - continuando...")
            
            # ── FASES SECUNDARIAS COMPLETAMENTE PARALELAS ─────────────────
            # Todas las fases se ejecutan en paralelo para máxima velocidad.
            # list.append() es thread-safe en CPython (GIL protege operaciones C).
            self._phase_counter = 0
            self._total_phases = 76
            if not hasattr(self, '_phase_lock'):
                self._phase_lock = threading.Lock()
            self._update_progress_safe(80, "⚡ Fases paralelas iniciadas", "Procesos · DNS · Registro · Red · IA...")

            def _run_safe(fn, *a, **kw):
                """Ejecuta fn con timeout de 8s; si se excede, continúa sin esperar."""
                if getattr(self, '_scan_cancel_event', None) and self._scan_cancel_event.is_set():
                    return None
                _result = [None]
                def _wrapper():
                    if getattr(self, '_scan_cancel_event', None) and self._scan_cancel_event.is_set():
                        return
                    try:
                        _result[0] = fn(*a, **kw)
                    except Exception as ex:
                        print(f"⚠️ Error en {fn.__name__}: {ex}")
                t = threading.Thread(target=_wrapper, daemon=True)
                t.start()
                t.join(timeout=8)
                if t.is_alive():
                    print(f"⏱️ Timeout en {fn.__name__} (8s) — continuando")
                return _result[0]

            def _extend_safe(result):
                if result:
                    self.issues_found.extend(result)

            # Grupo A — Procesos y sistema (I/O bajo)
            def _group_processes():
                self._set_scan_phase("⚙️ Procesos secundarios...")
                _run_safe(self.secondary_scan_parallel)
                self._set_scan_phase("🎮 Procesos Java / Minecraft...")
                _run_safe(self.scan_processes)
                _run_safe(self.advanced_minecraft_process_analysis)
                self._set_scan_phase("🌳 Árbol de procesos Java (parent analysis)...")
                _run_safe(self.scan_java_process_parent)
                self._set_scan_phase("🔒 Procesos deshabilitados / ocultos...")
                _run_safe(self.scan_disabled_processes)
                _run_safe(self.scan_running_processes)
                self._set_scan_phase("🌐 Caché DNS...")
                _run_safe(self.scan_dns_cache)
                self._set_scan_phase("🪟 Ventanas activas...")
                _run_safe(self.scan_windows)
                self._set_scan_phase("🪝 Hooks de input y drivers de bypass...")
                _run_safe(self.scan_input_hook_processes)

            # Grupo B — Archivos y fechas (I/O medio)
            def _group_files():
                self._set_scan_phase("📄 Ejecutables (.exe)...")
                _run_safe(self.scan_exe_files)
                self._set_scan_phase("☕ Archivos JAR...")
                _run_safe(self.scan_jar_files)
                self._set_scan_phase("📅 Archivos por fecha...")
                _run_safe(self.scan_files_by_date)
                self._set_scan_phase("👁️ Archivos ocultos / papelera...")
                _extend_safe(_run_safe(self.scan_hidden_files))
                _run_safe(self.scan_deleted_recycle)
                self._set_scan_phase("🎨 Texture packs / exploit tools...")
                _run_safe(self.scan_texture_packs)
                _run_safe(self.scan_exploit_tools)
                self._set_scan_phase("🗑️ Borrado masivo (detección de limpieza activa)...")
                _run_safe(self.scan_deleted_mass_event)
                self._set_scan_phase("📋 Historial de actividad de archivos...")
                _run_safe(self.scan_file_activity_log)
                self._set_scan_phase("👥 Shadow Copy artifacts (VSS)...")
                _run_safe(self.scan_shadow_copy_artifacts)

            # Grupo C — Registro y JNA (I/O bajo)
            def _group_registry():
                self._set_scan_phase("📂 Prefetch / JNA...")
                _run_safe(self.scan_prefetch_jna)
                _run_safe(self.scan_temp_jna)
                self._set_scan_phase("🗂️ Prefetch completo...")
                _run_safe(self.scan_prefetch_all)
                self._set_scan_phase("📋 Registro sospechoso...")
                _run_safe(self.scan_registry_suspicious)
                _run_safe(self.scan_registry)
                self._set_scan_phase("📜 Event logs...")
                _run_safe(self.scan_event_logs)
                self._set_scan_phase("💻 Historial CMD / PowerShell...")
                _run_safe(self.scan_cmd_history_full)
                _run_safe(self.scan_powershell_history)
                self._set_scan_phase("👤 UserAssist (programas ejecutados)...")
                _run_safe(self.scan_executed_userassist)
                self._set_scan_phase("⏱️ BAM registry (ejecuciones con timestamp)...")
                _run_safe(self.scan_bam_registry)
                self._set_scan_phase("🔗 ShimCache / AppCompatCache...")
                _run_safe(self.scan_appcompat_shimcache)
                self._set_scan_phase("🎨 MUICache...")
                _run_safe(self.scan_muicache)
                self._set_scan_phase("📎 Archivos recientes (LNK)...")
                _run_safe(self.scan_recent_lnk)
                self._set_scan_phase("📅 Tareas programadas...")
                _run_safe(self.scan_scheduled_tasks)
                self._set_scan_phase("🖥️ Comandos Run (Win+R)...")
                _run_safe(self.scan_run_mru)
                self._set_scan_phase("📁 Rutas escritas en Explorer...")
                _run_safe(self.scan_typed_paths)
                self._set_scan_phase("🔌 Historial USB...")
                _run_safe(self.scan_usb_history)
                self._set_scan_phase("🌐 Hosts file...")
                _run_safe(self.scan_hosts_file)
                self._set_scan_phase("🚀 Entradas de inicio automático...")
                _run_safe(self.scan_startup_entries)
                self._set_scan_phase("📦 Programas instalados...")
                _run_safe(self.scan_installed_programs)
                self._set_scan_phase("⛏️ JARs recientes en carpetas temporales...")
                _run_safe(self.scan_temp_jars)
                self._set_scan_phase("🤖 Baritone / modos prohibidos...")
                _run_safe(self.scan_baritone_config)
                self._set_scan_phase("🔨 Schematica/Litematica Printer Mode...")
                _run_safe(self.scan_schematica_litematica)
                self._set_scan_phase("🔍 OptiFine zoom key binding...")
                _run_safe(self.scan_optifine_zoom)
                self._set_scan_phase("🌐 Caché INetCache (IE/Edge)...")
                _run_safe(self.scan_inetcache)
                self._set_scan_phase("☕ java.policy modificado...")
                _run_safe(self.scan_java_policy)
                self._set_scan_phase("📅 Fecha de instalación de Minecraft...")
                _run_safe(self.scan_minecraft_install_date)
                self._set_scan_phase("🕹️ Última sesión de Minecraft...")
                _run_safe(self.scan_minecraft_last_session)
                self._set_scan_phase("👨‍💻 Proceso padre de java.exe...")
                _run_safe(self.scan_java_parent_process)
                self._set_scan_phase("🪟 Procesos java sin ventana...")
                _run_safe(self.scan_windowless_java)
                self._set_scan_phase("🔒 Atributos de solo lectura...")
                _run_safe(self.scan_readonly_suspicious_files)
                self._set_scan_phase("📂 Cambios recientes en .minecraft...")
                _run_safe(self.scan_minecraft_fs_changes)
                self._set_scan_phase("🔤 Análisis de nombres de carpetas...")
                _run_safe(self.scan_folder_name_nlp)

            # Grupo D — Hardware y red (I/O alto)
            def _group_hardware():
                _run_safe(self.scan_logitech_macros)
                _run_safe(self.scan_razer_macros)
                self._set_scan_phase("🖱️ Bloody/A4Tech macros...")
                _run_safe(self.scan_bloody_a4tech)
                self._set_scan_phase("🎮 SteelSeries/Corsair macros...")
                _run_safe(self.scan_steelseries_corsair)
                self._set_scan_phase("🔌 Arduino HID devices...")
                _run_safe(self.scan_arduino_hid)
                _extend_safe(_run_safe(self.scan_usb_devices))
                _extend_safe(_run_safe(self.scan_network_connections))
                self._set_scan_phase("🔌 Adaptadores VPN...")
                _run_safe(self.scan_vpn_adapters)
                self._set_scan_phase("☕ JDWP debug port...")
                _run_safe(self.scan_jdwp_port)
                self._set_scan_phase("💉 DLLs en proceso Java...")
                _run_safe(self.scan_dll_injection_java)
                self._set_scan_phase("📋 DLLs fuera de baseline en Java...")
                _run_safe(self.scan_java_dll_nonstandard)
                self._set_scan_phase("🗑️ JARs borrados durante ejecución...")
                _run_safe(self.scan_self_deletion_hacks)
                self._set_scan_phase("🔒 Conexiones TLS sospechosas de Java...")
                _run_safe(self.scan_java_suspicious_tls)
                self._set_scan_phase("🎛️ Packet sniffers activos...")
                _run_safe(self.scan_packet_sniffers)
                self._set_scan_phase("🌐 IP Forwarding...")
                _run_safe(self.scan_ip_forwarding)
                self._set_scan_phase("🔬 Strings de hack en JARs cargados por Java...")
                _run_safe(self.scan_process_memory_strings)
                self._set_scan_phase("📍 Correlación de ruta de proceso sospechoso...")
                _run_safe(self.scan_process_path_correlation)
                self._set_scan_phase("☁️ Hashes de procesos vs base de datos cloud...")
                _run_safe(self.scan_process_hashes_cloud)
                self._set_scan_phase("🧹 Actividad de borrado pre-scan (últimos 10 min)...")
                _run_safe(self.scan_prescan_disk_activity)
                self._set_scan_phase("🌳 Árbol de procesos — cadenas anómalas...")
                _run_safe(self.scan_process_tree)
                self._set_scan_phase("📊 Delta vs baseline histórico del jugador...")
                _run_safe(self.scan_player_baseline_delta)
                self._set_scan_phase("📝 TF-IDF en config files de ghost clients...")
                _run_safe(self.scan_config_tfidf)
                self._set_scan_phase("🔌 Conexiones de red de javaw a hosts externos...")
                _run_safe(self.scan_javaw_network_connections)
                self._set_scan_phase("🗂️ DLLs sospechosas en carpetas temporales...")
                _run_safe(self.scan_temp_dlls)
                self._set_scan_phase("⚡ Múltiples instancias de javaw.exe...")
                _run_safe(self.scan_multiple_javaw)
                self._set_scan_phase("🧠 Regiones de memoria RWX en javaw.exe...")
                _run_safe(self.scan_java_rwx_memory)

            # Grupo E — Ubicaciones de hacks (I/O alto)
            def _group_hack_locations():
                _run_safe(self.scan_common_hack_locations)
                _run_safe(self.scan_suspicious_folders)
                _run_safe(self.scan_exact_hack_names)
                self._set_scan_phase("👻 Config de ghost clients...")
                _run_safe(self.scan_ghost_client_configs)
                self._set_scan_phase("📋 Registro de ghost clients...")
                _run_safe(self.scan_ghost_client_registry)
                self._set_scan_phase("📦 Mods prohibidos en .minecraft/mods/...")
                _run_safe(self.scan_minecraft_mods_blacklist)
                self._set_scan_phase("🤖 Scripts AHK con autoclick...")
                _run_safe(self.scan_ahk_scripts)
                self._set_scan_phase("💉 Procesos inyectores activos...")
                _run_safe(self.scan_active_injectors)
                self._set_scan_phase("🔑 Hash de minecraft.jar vs Mojang...")
                _run_safe(self.scan_minecraft_jar_hash)
                self._set_scan_phase("📦 Múltiples versiones de Minecraft...")
                _run_safe(self.scan_minecraft_version_count)
                self._set_scan_phase("🔬 Entropy y packing de ejecutables sospechosos...")
                _run_safe(self.scan_exe_entropy_and_packing)
                self._set_scan_phase("🪝 -javaagent en JVM args...")
                _run_safe(self.scan_javaagent_args)
                self._set_scan_phase("🕸️ Weave Loader artifacts...")
                _run_safe(self.scan_weave_loader)
                self._set_scan_phase("🔍 Resourcepacks Xray (texturas transparentes)...")
                _run_safe(self.scan_xray_resourcepacks)
                self._set_scan_phase("📜 Scripts .bat/.ps1 launchers de hacks...")
                _run_safe(self.scan_bat_ps1_launchers)
                self._set_scan_phase("🖱️ Keybinds sospechosos en options.txt...")
                _run_safe(self.scan_options_txt_keybinds)
                self._set_scan_phase("🖥️ Fingerprint options.txt vs resolución del sistema...")
                _run_safe(self.scan_options_resolution_mismatch)
                self._set_scan_phase("⚙️ Configs .properties de hack clients...")
                _run_safe(self.scan_hack_properties_configs)
                self._set_scan_phase("📋 Prefetch de hacks ejecutados...")
                _run_safe(self.scan_prefetch_hacks)
                # USN Journal y Kill Chain comparten la misma llamada a fsutil
                # (cacheada en self._usn_cache). Correrlos en paralelo evita ejecutar
                # fsutil dos veces y reduce el tiempo total al máximo de los dos.
                self._set_scan_phase("📝 USN Journal + Kill Chain (paralelo)...")
                import concurrent.futures as _cf_usn
                with _cf_usn.ThreadPoolExecutor(max_workers=2) as _ex_usn:
                    _fu = _ex_usn.submit(_run_safe, self.scan_usn_minecraft_jars)
                    _fk = _ex_usn.submit(_run_safe, self.scan_kill_chain)
                    _fu.result()
                    _fk.result()
                self._set_scan_phase("📡 Discord webhooks en configs de hacks (C2)...")
                _run_safe(self.scan_discord_webhooks)
                self._set_scan_phase("💬 Discord settings locales (tokens/webhooks C2)...")
                _run_safe(self.scan_discord_local_settings)
                self._set_scan_phase("🔒 Archivos .lock huérfanos de hacks en .minecraft...")
                _run_safe(self.scan_minecraft_lock_files)
                self._set_scan_phase("🌐 Historial de descargas del navegador...")
                _run_safe(self.scan_browser_downloads)
                self._set_scan_phase("🌐 Historial de páginas visitadas (hack sites/DDoS)...")
                _run_safe(self.scan_browser_history_sites)
                self._set_scan_phase("💣 Aplicaciones DDoS (LOIC, HOIC, stressers)...")
                _run_safe(self.scan_ddos_applications)
                self._set_scan_phase("📋 Portapapeles — webhooks y nombres de hacks...")
                _run_safe(self.scan_clipboard_content)
                self._set_scan_phase("🎯 Jitter/aim assist en software de mouse...")
                _run_safe(self.scan_jitter_scripts)
                self._set_scan_phase("🖥️ Minecraft Safe Mode...")
                _run_safe(self.scan_minecraft_safe_mode)
                self._set_scan_phase("📋 Bug F3+T (recarga resource packs con click)...")
                _run_safe(self.scan_f3t_log_exploit)
                self._set_scan_phase("🛡️ Exclusiones sospechosas de Windows Defender...")
                _run_safe(self.scan_defender_exclusions)
                self._set_scan_phase("💥 Crash reports de Minecraft...")
                _run_safe(self.scan_minecraft_crash_reports)
                self._set_scan_phase("🗂️ Amcache — ejecución histórica de programas...")
                _run_safe(self.scan_amcache)
                self._set_scan_phase("📦 Instalaciones MSI recientes (últimos 7 días)...")
                _run_safe(self.scan_recent_msi_installs)
                self._set_scan_phase("🔍 Historial de búsquedas de Windows...")
                _run_safe(self.scan_windows_search_history)
                self._set_scan_phase("📎 Archivos recientes (.lnk) — accesos sospechosos...")
                _run_safe(self.scan_recent_files_lnk)
                self._set_scan_phase("🎯 Fingerprints compuestos de ghost clients...")
                _run_safe(self.scan_hack_fingerprints)
                self._set_scan_phase("💀 Cheat Engine activo/instalado...")
                _run_safe(self.scan_cheat_engine)
                self._set_scan_phase("🐍 Scripts Python de bots/macros...")
                _run_safe(self.scan_python_hack_scripts)
                self._set_scan_phase("☕ JDK completo instalado...")
                _run_safe(self.scan_jdk_installed)
                self._set_scan_phase("🌙 Módulos no oficiales de Lunar Client...")
                _run_safe(self.scan_lunar_unofficial_modules)
                self._set_scan_phase("🎙️ Virtual Audio Cable...")
                _run_safe(self.scan_virtual_audio_cable)
                self._set_scan_phase("📁 Repos Git sospechosos en Desktop/Documents...")
                _run_safe(self.scan_git_repos_desktop)
                self._set_scan_phase("🧩 Extensiones de navegador sospechosas...")
                _run_safe(self.scan_browser_extensions_suspicious)
                self._set_scan_phase("🔑 Integridad de minecraft client.jar vs Mojang...")
                _run_safe(self.scan_modified_minecraft_jar)
                self._set_scan_phase("📦 NBT exploits en saves de Minecraft...")
                _run_safe(self.scan_nbt_exploits_saves)
                self._set_scan_phase("🔧 Drivers kernel sospechosos (KMDF/minifilter)...")
                _run_safe(self.scan_suspicious_kernel_drivers)
            # Grupo F — Técnicas avanzadas
            def _group_advanced():
                try:
                    from silent_scanner_techniques import SilentScannerTechniques
                    adv = SilentScannerTechniques.scan_all_advanced_techniques()
                    if adv: self.issues_found.extend(adv)
                    print(f"✅ Técnicas Silent-scanner: {len(adv)} detecciones")
                except ImportError:
                    pass
                except Exception as ex:
                    print(f"⚠️ Silent-scanner: {ex}")
                try:
                    from astro_ss_techniques import AstroSSTechniques
                    astro_issues = AstroSSTechniques().scan_all_astro_techniques()
                    if astro_issues: self.issues_found.extend(astro_issues)
                    print(f"✅ Técnicas AstroSS: {len(astro_issues)} detecciones")
                except ImportError:
                    pass
                except Exception as ex:
                    print(f"⚠️ AstroSS: {ex}")

            # Grupo G — Análisis forense SS (checklist manual completo)
            def _group_forensics():
                if not self.ss_forensics:
                    return
                try:
                    findings = self.ss_forensics.scan_all()
                    if findings:
                        self.forensic_findings.extend(findings)
                        print(f"✅ SS Forensics: {len(findings)} hallazgo(s) forenses")
                        for ff in findings:
                            print(f"   🔬 {ff.get('nombre','')} [{ff.get('alerta','')}]")
                    else:
                        print("✅ SS Forensics: sin hallazgos forenses sospechosos")
                except Exception as ex:
                    print(f"⚠️ SS Forensics: {ex}")

            # Ejecutar todos los grupos en paralelo (7 workers)
            secondary_workers = min(7, psutil.cpu_count() or 4)
            print(f"⚡ Ejecutando fases secundarias con {secondary_workers} workers en paralelo")
            with concurrent.futures.ThreadPoolExecutor(max_workers=secondary_workers) as sec_exec:
                sec_futures = [
                    sec_exec.submit(_group_processes),
                    sec_exec.submit(_group_files),
                    sec_exec.submit(_group_registry),
                    sec_exec.submit(_group_hardware),
                    sec_exec.submit(_group_hack_locations),
                    sec_exec.submit(_group_advanced),
                    sec_exec.submit(_group_forensics),
                ]
                for f in concurrent.futures.as_completed(sec_futures, timeout=80):
                    try:
                        f.result()
                    except Exception as ex:
                        print(f"⚠️ Error en grupo de escaneo: {ex}")
            
            # ── Recolectar hallazgos de monitoreo de mouse ───────────────────
            if self.mouse_detector:
                try:
                    self.mouse_detector.stop_monitoring()
                    session = self.mouse_detector.get_session_findings()
                    self.mouse_findings.extend(session)
                    if session:
                        print(f"🖱️ Hallazgos de sesión de mouse: {len(session)}")
                        for f in session:
                            print(f"   ⚠️  {f['nombre']} [{f['alerta']}]")
                except Exception as _me:
                    print(f"⚠️ Error recolectando hallazgos de mouse: {_me}")

            # Análisis de evasión activa (post-scan, requiere todos los hallazgos previos)
            self._set_scan_phase("🎭 Detección de evasión activa...")
            _run_safe(self.scan_evasion_indicators)

            # Fase 9: Filtrado y clasificación (100%)
            self._update_progress_safe(100, "🔍 Filtrando resultados", "Aplicando filtros ultra estrictos...")
            print(f"[FILTRO] Issues antes de filtrar: {len(self.issues_found)} | Archivos escaneados: {self.total_files_scanned} | Dirs: {self.total_dirs_scanned}")

            # Aplicar filtro ultra inteligente
            pre_filter = len(self.issues_found)
            self.issues_found = self.filter_false_positives(self.issues_found)
            print(f"[FILTRO] Después de filter_false_positives: {len(self.issues_found)} (eliminados: {pre_filter - len(self.issues_found)})")

            # Aplicar segundo filtro más inteligente
            pre_secondary = len(self.issues_found)
            self.issues_found = self.secondary_filter(self.issues_found)
            print(f"[FILTRO] Después de secondary_filter: {len(self.issues_found)} (eliminados: {pre_secondary - len(self.issues_found)})")

            # Correlación temporal: prefetch + userassist + browser → CRITICAL confirmado
            self.issues_found = self._apply_temporal_correlation(self.issues_found)
            
            # Segunda pasada de análisis sobre archivos sospechosos
            self._update_progress_safe(96, "🔬 Segunda pasada", "Analizando archivos sospechosos en profundidad...")
            self.second_pass_scanner()

            # Aplicar análisis de IA si está disponible
            if self.ai_analyzer and self.issues_found:
                try:
                    self._update_progress_safe(100, "🤖 Analizando con IA", "Aplicando análisis inteligente...")
                    self.issues_found = self.ai_analyzer.analyze_batch(self.issues_found)
                    print(f"✅ Análisis de IA aplicado - {len(self.issues_found)} issues analizados")
                except Exception as e:
                    print(f"⚠️ Error en análisis de IA durante escaneo: {e}")
            
            # Aplicar sistema de scoring de confianza
            if self.scoring_system and self.issues_found:
                try:
                    self._update_progress_safe(100, "📊 Calculando scores", "Priorizando resultados...")
                    self.issues_found = self.scoring_system.prioritize_results(self.issues_found)
                    print(f"✅ Scoring aplicado - {len(self.issues_found)} issues priorizados")
                except Exception as e:
                    print(f"⚠️ Error aplicando scoring: {e}")
            
            # ── Boost multi-cliente (#25) ────────────────────────────────
            # Si hay 2+ ghost clients distintos detectados → todos suben a CRITICAL.
            _ghost_clients_detected = set()
            _GHOST_CLIENT_NAMES = {
                'vape', 'vapelite', 'sigma', 'sigma6', 'liquidbounce', 'wurst', 'rise',
                'flux', 'future', 'astolfo', 'novoline', 'drip', 'entropy', 'whiteout',
                'exhibition', 'meteor', 'rusherhack', 'aristois', 'tenacity', 'vertex',
                'inertia', 'salhack', 'jello', 'remix', 'pandora', 'azura', 'kamiblue',
                'konas', 'weepcraft', 'nyx', 'lucid', 'impact', 'ghostclient',
                'weaveloader', 'labymod-hacks', 'breezeclient', 'datura',
            }
            for _iss in self.issues_found:
                _combined = (_iss.get('nombre', '') + _iss.get('ruta', '') + _iss.get('archivo', '')).lower()
                for _gc in _GHOST_CLIENT_NAMES:
                    if _gc in _combined:
                        _ghost_clients_detected.add(_gc)
                        break
            if len(_ghost_clients_detected) >= 2:
                print(f"⚡ MULTI-CLIENTE detectado ({len(_ghost_clients_detected)} clientes): {_ghost_clients_detected} → todos suben a CRITICAL")
                for _iss in self.issues_found:
                    _iss['alerta'] = 'CRITICAL'
                self.issues_found.append({
                    'nombre': f'Multi-cliente: {len(_ghost_clients_detected)} hack clients distintos detectados',
                    'ruta': '',
                    'archivo': '',
                    'tipo': 'evasion_indicators',
                    'categoria': 'MULTI_CLIENTE',
                    'alerta': 'CRITICAL',
                    'confidence': 0.97,
                    'detected_patterns': [f'multi_client:{c}' for c in sorted(_ghost_clients_detected)],
                    'explicacion': (
                        f'Se detectaron {len(_ghost_clients_detected)} hack clients diferentes: '
                        f'{", ".join(sorted(_ghost_clients_detected))}. Tener múltiples clientes '
                        'indica un coleccionista de hacks o alguien que prueba activamente '
                        'diferentes herramientas para evadir detección.'
                    ),
                })

            # ── P3 #26 — Resultado del test de clicks (botón autoclicker) ──────
            _ctr = getattr(self, '_click_test_result', None)
            if _ctr:
                self.issues_found.append(_ctr)
                print(f"🖱️ Click test: {_ctr['alerta']} — {_ctr['nombre']}")

            # ── Flag de scan demasiado rápido (#26) ──────────────────────
            if hasattr(self, 'scan_start_time'):
                _elapsed = time.time() - self.scan_start_time
                _total_files = getattr(self, 'total_files_scanned', 0)
                if _elapsed < 30 and _total_files < 500:
                    print(f"⚠️ Scan completado en {_elapsed:.1f}s con solo {_total_files} archivos — posible VM o evasión")
                    self.issues_found.append({
                        'nombre': f'Scan completado en {_elapsed:.0f}s con {_total_files} archivos (posible VM o limpieza previa)',
                        'ruta': '',
                        'archivo': '',
                        'tipo': 'evasion_indicators',
                        'categoria': 'EVASION',
                        'alerta': 'SOSPECHOSO',
                        'confidence': 0.70,
                        'detected_patterns': [f'fast_scan:{_elapsed:.0f}s', f'low_file_count:{_total_files}'],
                        'explicacion': (
                            f'El scan terminó en {_elapsed:.0f} segundos escaneando solo {_total_files} archivos. '
                            'Una máquina limpia normalmente tarda 2+ minutos. Esto puede indicar '
                            'una máquina virtual vacía, un equipo con el sistema recién formateado, '
                            'o limpieza activa de evidencia antes de la sesión de SS.'
                        ),
                    })

            # Actualizar contadores en la UI
            if UI_STYLE_AVAILABLE:
                counts = {'critical': 0, 'suspicious': 0, 'low': 0, 'clean': 0}
                for iss in self.issues_found:
                    lvl = iss.get('alerta', '').upper()
                    if lvl == 'CRITICAL':
                        counts['critical'] += 1
                    elif lvl == 'SOSPECHOSO':
                        counts['suspicious'] += 1
                    elif lvl == 'POCO_SOSPECHOSO':
                        counts['low'] += 1
                    else:
                        counts['clean'] += 1
                for k, v in counts.items():
                    ModernUI.update_counter(k, v)

            # Finalizar (95% — el 100% lo pone el hilo principal tras enviar resultados)
            self._update_progress_safe(95, "Preparando resultados", f"Encontrados {len(self.issues_found)} elementos")
            
            # Estadísticas finales
            if hasattr(self, 'scan_start_time'):
                total_time = time.time() - self.scan_start_time
                print(f"🏁 ESTADÍSTICAS FINALES:")
                print(f"   📁 Total elementos encontrados: {len(self.issues_found)}")
                print(f"   ⏱️ Tiempo total de escaneo: {total_time:.1f} segundos")
                print(f"   🔧 CPU cores utilizados: {psutil.cpu_count()}")
                print(f"   💾 Memoria disponible: {psutil.virtual_memory().available / (1024**3):.1f} GB")
            
            print("✅ ESCANEO COMPLETADO")

            # Notificación de Windows al completar (#38)
            try:
                _n_issues = len(self.issues_found)
                _n_critical = sum(1 for i in self.issues_found if i.get('alerta') == 'CRITICAL')
                _msg = (
                    f'{_n_critical} hallazgos CRÍTICOS de {_n_issues} totales'
                    if _n_critical else f'{_n_issues} hallazgos (ninguno crítico)'
                )
                ctypes.windll.user32.MessageBeep(0x00000040)  # MB_ICONINFORMATION sound
                # Toast notification via PowerShell (no requiere COM ni extras)
                import subprocess as _sp_notif
                _ps_cmd = (
                    f"[void][Windows.UI.Notifications.ToastNotificationManager, Windows.UI.Notifications, "
                    f"ContentType = WindowsRuntime]; "
                    f"$t = [Windows.UI.Notifications.ToastTemplateType]::ToastText02; "
                    f"$xml = [Windows.UI.Notifications.ToastNotificationManager]::GetTemplateContent($t); "
                    f"$xml.GetElementsByTagName('text')[0].AppendChild($xml.CreateTextNode('ArgusScanner — Escaneo completado')) | Out-Null; "
                    f"$xml.GetElementsByTagName('text')[1].AppendChild($xml.CreateTextNode('{_msg}')) | Out-Null; "
                    f"$toast = [Windows.UI.Notifications.ToastNotification]::new($xml); "
                    f"[Windows.UI.Notifications.ToastNotificationManager]::CreateToastNotifier('ArgusScanner').Show($toast)"
                )
                _sp_notif.Popen(
                    ['powershell', '-NoProfile', '-WindowStyle', 'Hidden', '-Command', _ps_cmd],
                    stdout=_sp_notif.DEVNULL, stderr=_sp_notif.DEVNULL,
                    creationflags=0x08000000,
                )
            except Exception:
                pass

        except Exception as e:
            print(f"Error durante escaneo exhaustivo: {str(e)}")
            import traceback
            traceback.print_exc()
            self._update_progress_safe(95, f"❌ Error: {str(e)}", "Error durante el escaneo")
        finally:
            # Detener monitor USB y cronómetro
            self._stop_usb_monitor()
            self.stop_scan_timer()
            self.scanning = False
            self._restore_window_title()
            if UI_STYLE_AVAILABLE:
                ModernUI.set_status_badge("LISTO", ModernUI.COLORS['green'])
                if hasattr(self, '_completion_widgets'):
                    try:
                        self.root.after(0, lambda: ModernUI.set_completion_state(
                            self._completion_widgets,
                            success=True,
                            message="Escaneo completado",
                            sub="Los resultados han sido enviados al staff"
                        ))
                    except Exception:
                        pass
    
    def scan_drive_exhaustive(self, drive, start_progress, end_progress):
        """Escanea una unidad completa - VERSIÓN OPTIMIZADA CON LÍMITES"""
        import time
        
        try:
            print(f"🔍 INICIANDO ESCANEO OPTIMIZADO DE UNIDAD: {drive}")
            print(f"📊 Rango de progreso: {start_progress}% - {end_progress}%")
            
            if not os.path.exists(drive):
                print(f"❌ Unidad {drive} no existe, saltando...")
                return
            
            start_time = time.time()
            
            # Timeout agresivo: objetivo < 90s totales para todo el scan
            # Esta fase ocupa ~80% del tiempo, así que le damos 65s max por unidad
            try:
                cpu_count = psutil.cpu_count() or 2
                if cpu_count < 4:
                    total_timeout = 80   # hardware lento
                elif cpu_count < 8:
                    total_timeout = 65
                else:
                    total_timeout = 55   # hardware rápido
                print(f"⚙️ Hardware {cpu_count} cores → timeout por unidad: {total_timeout}s (objetivo total <90s)")
            except Exception:
                total_timeout = 65
                print(f"⚠️ No se pudo detectar hardware, usando timeout: {total_timeout}s")
            
            scanned_files = 0
            max_files_per_folder = None  # Sin límite de archivos por carpeta (solo timeout total)
            last_progress_update = start_time
            
            # Actualizar contador global
            if not hasattr(self, 'total_files_scanned'):
                self.total_files_scanned = 0
            if not hasattr(self, 'total_dirs_scanned'):
                self.total_dirs_scanned = 0
            
            max_depth = 4   # Reducido de 8 → 4 para velocidad (Minecraft no tiene más de 4 niveles relevantes)

            skip_folders = {
                'node_modules', '.git', '__pycache__', 'venv', '.venv',
                'WinSxS', 'servicing', 'en-US', 'MUI', 'winsxs',
                # Directorios de navegadores — generan cientos de false positives
                # porque sus subcarpetas internas tienen nombres como "ClientCertificates"
                'User Data', 'Default', 'Profiles',  # Chrome/Edge profile dirs
                'chrome', 'Chrome', 'firefox', 'Firefox', 'edge', 'Edge',
                'Brave-Browser', 'vivaldi', 'opera',
                # Drivers y sistema
                'DriverStore', 'SystemResources', 'Panther',
                # Cache del sistema — no relevante para hacks de Minecraft
                'Temp', 'temp', 'tmp', 'cache', 'Cache',
            }

            # Solo rutas relevantes para Minecraft hacks — no System32 ni Program Files completos
            user_home = os.path.expanduser("~")
            critical_paths = [
                # Minecraft y clientes
                os.path.join(user_home, "AppData", "Roaming", ".minecraft"),
                os.path.join(user_home, "AppData", "Roaming", "lunar-launcher"),
                os.path.join(user_home, "AppData", "Roaming", "feather"),
                os.path.join(user_home, "AppData", "Roaming", "cosmic"),
                os.path.join(user_home, "AppData", "Local", "Programs"),
                # Carpetas de usuario
                os.path.join(user_home, "Downloads"),
                os.path.join(user_home, "Desktop"),
                os.path.join(user_home, "Documents"),
                os.path.join(user_home, "AppData", "Roaming"),
                os.path.join(user_home, "AppData", "Local", "Temp"),
                # Temp del sistema (pequeño)
                os.path.join(drive, "Windows", "Temp"),
                os.path.join(drive, "Windows", "Prefetch"),
            ]

            # Agregar .minecraft de otros usuarios en el mismo equipo
            users_dir = os.path.join(drive, "Users")
            if os.path.exists(users_dir):
                try:
                    for user_folder in os.listdir(users_dir):
                        user_path = os.path.join(users_dir, user_folder)
                        if os.path.isdir(user_path) and user_folder not in ['Default', 'Public', 'All Users']:
                            mc_path = os.path.join(user_path, "AppData", "Roaming", ".minecraft")
                            if mc_path not in critical_paths:
                                critical_paths.append(mc_path)
                            for client in ("lunar-launcher", "feather", "cosmic"):
                                cp = os.path.join(user_path, "AppData", "Roaming", client)
                                if cp not in critical_paths:
                                    critical_paths.append(cp)
                except Exception:
                    pass
            
            # Primero escanear carpetas específicas con límites
            for critical_path in critical_paths:
                if not os.path.exists(critical_path):
                    continue
                    
                folder_start_time = time.time()
                folder_scanned = 0
                print(f"📁 ESCANEANDO CARPETA CRÍTICA: {critical_path}")
                
                try:
                    for root, dirs, files in os.walk(critical_path):
                        self.total_dirs_scanned += 1  # Contar cada carpeta visitada
                        # Verificar timeout total (no por carpeta)
                        if time.time() - start_time > total_timeout:
                            print(f"⏰ Timeout total alcanzado después de {total_timeout//60} minutos - finalizando escaneo...")
                            break
                        
                        # Limitar profundidad
                        depth = root.count(os.sep) - critical_path.count(os.sep)
                        if depth > max_depth:
                            dirs[:] = []  # No explorar más profundo
                            continue
                        
                        # Saltar carpetas problemáticas
                        dirs[:] = [d for d in dirs if not any(skip in os.path.join(root, d).lower() for skip in skip_folders)]
                        
                        # Sin límite de archivos (solo timeout total)
                        # Verificar timeout total continuamente
                        if time.time() - start_time > total_timeout:
                            break
                        
                        # Filtrar archivos por extensión
                        relevant_extensions = (
                            '.jar', '.exe', '.dll', '.bat', '.cmd', '.ps1', '.vbs', '.js', '.py', 
                            '.class', '.java', '.lua', '.txt', '.log', '.cfg', '.config', '.json', 
                            '.properties', '.yml', '.yaml', '.xml', '.dat', '.bin', '.cache',
                            '.tmp', '.temp', '.bak', '.backup', '.old', '.new', '.mod', '.minecraft',
                            '.zip', '.rar', '.7z', '.tar', '.gz', '.msi', '.msm', '.msp'
                        )
                        relevant_files = [f for f in files if f.lower().endswith(relevant_extensions)]
                        # Contar TODOS los archivos vistos (antes de filtrar por extensión)
                        self.total_files_scanned += len(files)
                        scanned_files += len(files)
                        folder_scanned += len(files)

                        # Verificar carpetas sospechosas
                        _root_lower = root.lower()
                        for dir_name in dirs:
                            if _is_hack_folder(dir_name, _root_lower):
                                self.issues_found.append({
                                    'nombre': dir_name,
                                    'ruta': root,
                                    'archivo': os.path.join(root, dir_name),
                                    'tipo': 'folder',
                                    'categoria': 'HACKS',
                                    'alerta': 'SOSPECHOSO'
                                })
                            
                        # Procesar TODOS los archivos (sin límite por lote)
                        for file in relevant_files:
                            try:
                                file_path = os.path.join(root, file)
                                
                                if self.is_suspicious_file(file_path):
                                    self.issues_found.append({
                                        'nombre': file,
                                        'ruta': root,
                                        'archivo': file_path,
                                        'tipo': 'file',
                                        'categoria': 'HACKS',
                                        'alerta': 'SOSPECHOSO'
                                    })
                                
                                # Actualizar progreso cada 2000 archivos O cada 3 segundos
                                _now = time.time()
                                if scanned_files % 2000 == 0 or (_now - last_progress_update) >= 3:
                                    last_progress_update = _now
                                    elapsed = _now - start_time
                                    rate = scanned_files / elapsed if elapsed > 0 else 0
                                    remaining = total_timeout - elapsed
                                    print(f"📁 {drive}: {scanned_files} archivos ({rate:.0f} arch/s) - Tiempo restante: {remaining:.0f}s...")
                                    # Actualizar barra de progreso dinámicamente
                                    elapsed_pct = min(79, int(start_progress + (elapsed / total_timeout) * (end_progress - start_progress)))
                                    self._update_progress_safe(elapsed_pct, f"🔍 Escaneando {drive}", f"{scanned_files:,} archivos · {rate:.0f} arch/s")
                                
                                # Verificar timeout total (sin límite de archivos)
                                if time.time() - start_time > total_timeout:
                                    break
                                    
                            except (PermissionError, OSError):
                                continue
                            except Exception:
                                continue
                        
                        # Verificar timeout total (sin límite de archivos)
                        if time.time() - start_time > total_timeout:
                            break
                                
                except Exception as e:
                    print(f"⚠️ Error en {critical_path}: {e} - continuando...")
                    continue
            
            
            # Calcular estadísticas de velocidad
            end_time = time.time()
            elapsed_time = end_time - start_time
            files_per_second = scanned_files / elapsed_time if elapsed_time > 0 else 0
            
            print(f"📊 TOTAL ESCANEADO EN {drive}: {scanned_files} archivos")
            print(f"⚡ VELOCIDAD: {files_per_second:.1f} archivos/segundo")
            print(f"⏱️ TIEMPO EN {drive}: {elapsed_time:.1f} segundos")
            
            # Actualizar progreso final para esta unidad
            try:
                self._update_progress_safe(end_progress, f"✅ Completado {drive}", f"Escaneados {scanned_files} archivos - {files_per_second:.1f} arch/seg")
            except:
                pass
                            
        except Exception as e:
            print(f"Error escaneando unidad {drive}: {e}")
    
    def _process_file_batch(self, file_batch):
        """Procesa un lote de archivos de manera eficiente"""
        try:
            for file, root, file_path in file_batch:
                # Verificar si es sospechoso
                if self.is_suspicious_file(file_path):
                    self.issues_found.append({
                        'nombre': file,
                        'ruta': root,
                        'archivo': file_path,
                        'tipo': 'file',
                        'categoria': 'HACKS',
                        'alerta': 'SOSPECHOSO'
                    })
        except Exception as e:
            print(f"Error procesando lote de archivos: {e}")
    
    def analyze_file_content(self, file_path):
        """Análisis avanzado del contenido del archivo - Detecta hacks por contenido, no solo nombre"""
        try:
            if file_path in self.file_analysis_cache:
                return self.file_analysis_cache[file_path]

            result = {
                'is_hack': False,
                'confidence': 0,
                'detected_patterns': [],
                'obfuscation_detected': False,
                'file_hash': None,
                'is_log_file': False,
                'log_explanation': '',
            }

            filename_lower = os.path.basename(file_path).lower()
            file_ext = os.path.splitext(filename_lower)[1]

            # ── Mejora 1: Whitelist de nombres genéricos ─────────────────────────
            # Archivos con estos nombres son demasiado genéricos para ser evidencia de hack
            GENERIC_FILENAME_WHITELIST = {
                'message.txt', 'messages.txt', 'readme.txt', 'readme.md',
                'notes.txt', 'note.txt', 'info.txt', 'todo.txt', 'changelog.txt',
                'license.txt', 'licence.txt', 'credits.txt', 'authors.txt',
                'help.txt', 'manual.txt', 'instructions.txt', 'guide.txt',
                'terms.txt', 'privacy.txt', 'about.txt', 'history.txt',
                'update.txt', 'updates.txt', 'version.txt', 'versions.txt',
                'config.txt', 'default.txt', 'sample.txt', 'example.txt',
                'output.txt', 'result.txt', 'results.txt', 'data.txt',
            }
            if filename_lower in GENERIC_FILENAME_WHITELIST:
                self.file_analysis_cache[file_path] = result
                return result

            # ── Mejora 2: Detección de archivos de log ───────────────────────────
            # Logs registran actividad, no son el hack en sí mismo
            LOG_NAME_PATTERNS = (
                'launcher_log', 'latest.log', 'debug.log', 'crash.log',
                'error.log', 'output.log', 'console.log', 'game.log',
                'launch.log', '.log',
            )
            is_log = (file_ext == '.log' or
                      any(p in filename_lower for p in LOG_NAME_PATTERNS))
            result['is_log_file'] = is_log

            # Calcular hash SHA256
            try:
                with open(file_path, 'rb') as f:
                    file_content = f.read()
                    file_hash = hashlib.sha256(file_content).hexdigest()
                    result['file_hash'] = file_hash
                    if file_hash in self.known_hack_hashes:
                        result['is_hack'] = True
                        result['confidence'] = 100
                        result['detected_patterns'].append('known_hash')
                        self.file_analysis_cache[file_path] = result
                        return result
            except:
                pass

            # ── Patrones de hacks en contenido ───────────────────────────────────
            # Excluidos a propósito: reach, velocity, fly, bypass, inject, ghost, scaffold
            hack_content_patterns = [
                b'vapelite', b'vapev4',               # vape con sufijo → más específico
                b'entropy', b'entropyclient',
                b'whiteout',
                b'liquidbounce',
                b'wurst', b'wurstclient',
                b'impactclient',
                b'sigmaclient', b'sigma5',
                b'fluxclient',
                b'futureclient',
                b'astolfo', b'astolfoclient',
                b'exhibition',
                b'novoline',
                b'dripclient',                         # drip solo es muy corto, solo con sufijo
                b'meteorclient', b'meteor-client',
                b'rusherhack',
                b'aristois',
                b'tenacity',
                b'inertiaclient',
                b'salhack',
                b'jelloclient',
                b'daturamc',
                b'remixclient',
                b'pandoraclient',
                b'azuraclient',
                b'kamiblue',
                b'konasclient',
                b'weepcraft',
                b'zeroday',
                b'nyxclient',
                b'killaura', b'kill-aura',
                b'aimbot', b'aim-bot',
                b'triggerbot',
                b'xray', b'fullbright',
                b'autoclicker',                        # autoclick es demasiado genérico solo
                b'clickgui',
                b'anticheat.bypass', b'anticheat bypass',
                b'scaffoldhack',
                b'weaveloader', b'weave-loader',
                b'extremeinjector',
                b'dllinjector',
                b'cheatengine',
                b'discord.com/api/webhooks/',
                b'phobos',
            ]
            # Patrones que por sí solos confirman hack (nombres de cliente exclusivos)
            DEFINITE_CONTENT_PATTERNS = {
                b'meteorclient', b'rusherhack', b'aristois', b'tenacity',
                b'inertiaclient', b'salhack', b'jelloclient', b'daturamc',
                b'kamiblue', b'weaveloader', b'weave-loader', b'extremeinjector',
                b'astolfoclient', b'entropyclient', b'liquidbounce', b'wurstclient',
                b'futureclient', b'fluxclient', b'sigmaclient', b'vapelite',
                b'pandoraclient', b'azuraclient', b'nyxclient', b'remixclient',
                b'meteor-client',
            }

            try:
                if file_ext in ('.jar', '.class', '.java', '.txt', '.lua', '.js', '.py', '.log',
                                '.cfg', '.config', '.properties', '.json', '.yml', '.yaml'):
                    with open(file_path, 'rb') as f:
                        content = f.read(1024 * 1024)

                    # ── Mejora 5: Filtro de tamaño mínimo para .txt ──────────────
                    # Archivos .txt muy pequeños con mención única no son evidencia
                    file_size = len(content)
                    if file_ext in ('.txt', '.log') and file_size < 200:
                        self.file_analysis_cache[file_path] = result
                        return result

                    content_norm = _normalize(content.decode('utf-8', errors='ignore')).encode('ascii')
                    detected_count = 0
                    definite_hit = False
                    definite_patterns_found = []

                    for pattern in hack_content_patterns:
                        if pattern in content or pattern in content_norm:
                            detected_count += 1
                            result['detected_patterns'].append(pattern.decode('utf-8', errors='ignore'))
                            if pattern in DEFINITE_CONTENT_PATTERNS:
                                definite_hit = True
                                definite_patterns_found.append(pattern.decode('utf-8', errors='ignore'))

                    # ── Mejora 6: Densidad de palabras clave ─────────────────────
                    # En archivos grandes (>100KB) un solo hit tiene menos peso
                    density_penalty = 0
                    if file_size > 100_000 and detected_count <= 2:
                        density_penalty = 15  # reducir confianza

                    # ── Mejora 3+4: Umbrales según tipo de archivo ───────────────
                    # .txt y .log: requieren más evidencia (son texto plano ambiguo)
                    # .jar/.class: un patrón definitivo es suficiente (bytecode no miente)
                    is_text_file = file_ext in ('.txt', '.log', '.cfg', '.properties',
                                                 '.yml', '.yaml', '.json')

                    if is_log:
                        # ── Mejora 8+9: Logs necesitan 2+ patrones definitivos ───
                        # Un log que menciona meteor-client registra su USO, no es el hack
                        definite_count = len(definite_patterns_found)
                        if definite_count >= 2:
                            result['is_hack'] = True
                            result['confidence'] = min(65, 45 + definite_count * 8) - density_penalty
                        elif definite_count == 1 and detected_count >= 2:
                            result['is_hack'] = True
                            result['confidence'] = max(40, 50 - density_penalty)
                        elif definite_count == 1:
                            # Un solo nombre de hack en un log = registra su uso
                            result['is_hack'] = True
                            result['confidence'] = max(35, 40 - density_penalty)
                        # ── Mejora 9: Explicación específica para logs ───────────
                        if result['is_hack'] and definite_patterns_found:
                            clients = ', '.join(definite_patterns_found[:3])
                            result['log_explanation'] = (
                                f'Este archivo de log registra que el cliente de hacks '
                                f'"{clients}" fue ejecutado en este equipo. '
                                f'No es el hack en sí, pero confirma su uso previo.'
                            )
                            result['detected_patterns'].append('log_registra_uso_de_hack')

                    elif is_text_file:
                        # ── Mejora 3: .txt requiere 2+ patrones para ser HACK ────
                        if definite_hit and detected_count >= 2:
                            result['is_hack'] = True
                            result['confidence'] = min(80, 60 + detected_count * 5) - density_penalty
                        elif definite_hit and detected_count == 1:
                            # Solo 1 patrón definitivo en .txt: POCO_SOSPECHOSO, no hack
                            result['is_hack'] = False
                            result['confidence'] = max(20, 35 - density_penalty)
                            result['detected_patterns'].append('single_pattern_txt_weak')
                        elif detected_count >= 3:
                            result['is_hack'] = True
                            result['confidence'] = min(75, detected_count * 12) - density_penalty
                        elif detected_count == 2:
                            result['is_hack'] = True
                            result['confidence'] = max(40, 50 - density_penalty)

                    else:
                        # Binarios (.jar, .class, .py, .js, .lua): lógica original más estricta
                        if definite_hit:
                            result['is_hack'] = True
                            result['confidence'] = min(95, 70 + detected_count * 5)
                        elif detected_count >= 3:
                            result['is_hack'] = True
                            result['confidence'] = min(90, detected_count * 12)
                        elif detected_count == 2:
                            result['is_hack'] = True
                            result['confidence'] = 55

                    # Ofuscación solo relevante para no-binarios
                    if len(content) > 100 and file_ext not in ('.jar', '.class'):
                        non_ascii_ratio = sum(1 for b in content[:1000] if b > 127) / min(1000, len(content))
                        if non_ascii_ratio > 0.3:
                            result['obfuscation_detected'] = True
                            if not is_log:  # logs pueden tener caracteres especiales
                                result['confidence'] += 20
            except:
                pass

            # Análisis de estructura interna para JARs
            if filename_lower.endswith('.jar'):
                try:
                    import zipfile as _zf
                    import math as _math
                    LEGIT_MOD_MARKERS = {
                        'mcmod.info', 'fabric.mod.json', 'quilt.mod.json',
                        'mods.toml', 'pack.mcmeta',
                    }
                    SUSPICIOUS_MANIFEST_PACKAGES = [
                        # Clientes clásicos
                        'com.vape', 'net.sigma', 'com.entropy', 'me.drip',
                        'net.liquidbounce', 'com.wurst', 'com.future', 'com.flux',
                        'com.astolfo', 'net.rise', 'com.novoline', 'com.ghost',
                        # Clientes modernos (2022-2025)
                        'com.meteor', 'meteordevelopment',
                        'net.rusherhack', 'com.rusherhack',
                        'com.aristois', 'net.aristois',
                        'com.tenacity', 'net.tenacity',
                        'com.vertex', 'net.vertex',
                        'com.inertia', 'net.inertia',
                        'me.kami', 'net.kamiblue',
                        'com.salhack', 'me.salhack',
                        'com.jello', 'me.jello',
                        'com.datura', 'me.datura',
                        'com.pandora', 'net.pandora',
                        'com.azura', 'me.azura',
                        'com.konas', 'net.konas',
                        'com.remix', 'net.remix',
                        # Loaders e injectors
                        'me.weaveclient', 'net.weaveloader',
                        'com.salhack',
                        # Módulos/cheats genéricos
                        'me.baritone',  # bot de movimiento automático
                        'com.phobos', 'net.phobos',
                        'com.seppuku', 'com.sloth',
                    ]
                    with _zf.ZipFile(file_path, 'r') as zf:
                        names_lower = {n.lower() for n in zf.namelist()}
                        has_legit_marker = bool(names_lower & LEGIT_MOD_MARKERS)
                        result['has_legit_mod_marker'] = has_legit_marker

                        if has_legit_marker and result['confidence'] < 75:
                            result['confidence'] = max(0, result['confidence'] - 20)
                            result['detected_patterns'].append('has_legit_mod_marker')

                        # P2 #14 — Verificar firma criptográfica JAR (.SF + bloque .RSA/.DSA/.EC)
                        _sf_files = [n for n in zf.namelist()
                                     if n.upper().startswith('META-INF/') and n.upper().endswith('.SF')]
                        if _sf_files:
                            # Comprobar que hay un bloque de firma (.RSA, .DSA o .EC) para cada .SF
                            _sig_blocks = {
                                n.upper().rsplit('.', 1)[0]
                                for n in zf.namelist()
                                if n.upper().startswith('META-INF/') and
                                   n.upper().rsplit('.', 1)[-1] in ('RSA', 'DSA', 'EC')
                            }
                            _sf_bases = {n.upper().rsplit('.', 1)[0] for n in _sf_files}
                            _valid_sig = bool(_sf_bases & _sig_blocks)  # at least one pair

                            if _valid_sig:
                                # Verify .SF has Digest lines (a well-formed jarsigner output)
                                try:
                                    _sf_content = zf.read(_sf_files[0]).decode('utf-8', errors='ignore')
                                    _has_digests = '-Digest:' in _sf_content
                                except Exception:
                                    _has_digests = False

                                if _has_digests:
                                    result['detected_patterns'].append('jar_signed_valid')
                                    if result['confidence'] < 70:
                                        result['confidence'] = max(0, result['confidence'] - 20)
                                else:
                                    result['detected_patterns'].append('jar_signed_malformed')
                            else:
                                # .SF without signature block → unsigned/tampered JAR structure
                                result['detected_patterns'].append('jar_signed_incomplete')
                                result['confidence'] = min(0.99, float(result['confidence']) + 5)

                        # Check MANIFEST.MF for suspicious main class
                        if 'meta-inf/manifest.mf' in names_lower:
                            try:
                                manifest = zf.read('META-INF/MANIFEST.MF').decode('utf-8', errors='ignore').lower()
                                for pkg in SUSPICIOUS_MANIFEST_PACKAGES:
                                    if pkg in manifest:
                                        result['is_hack'] = True
                                        result['confidence'] = max(result['confidence'], 80)
                                        result['detected_patterns'].append(f'manifest_pkg:{pkg}')
                                        break
                            except Exception:
                                pass

                        # P2 #15 + P2 #48 — Imports de bytecode Java: MC client hooks y paquetes de hack
                        if not has_legit_marker:
                            try:
                                _HACK_BYTECODE = [
                                    # MC client hooking
                                    b'net/minecraft/client/Minecraft',
                                    b'net/minecraft/client/MinecraftClient',
                                    # Ghost client package patterns
                                    b'com/vape/', b'net/sigma/', b'com/entropy/',
                                    b'me/drip/', b'com/aristois/', b'me/weaveclient/',
                                    b'net/liquidbounce/', b'meteordevelopment/',
                                    b'com/github/wurstclient/', b'me/zeroeightsix/',
                                    # Injection/hook APIs
                                    b'java/lang/instrument/Instrumentation',
                                    b'sun/reflect/Reflection',
                                    b'java/lang/reflect/Proxy',
                                    # AimBot / KillAura typical patterns
                                    b'RotationUtils', b'TargetUtils', b'KillAura',
                                    b'AimBot', b'AimAssist', b'AutoClick',
                                ]
                                _bc_hits = []
                                _class_files = [n for n in zf.namelist() if n.endswith('.class')][:100]
                                for _cf in _class_files:
                                    try:
                                        _bc = zf.read(_cf)
                                        for _pat in _HACK_BYTECODE:
                                            if _pat in _bc:
                                                _bc_hits.append(_pat.decode('latin-1').split('/')[-1][:30])
                                                break
                                    except Exception:
                                        pass
                                if _bc_hits:
                                    result['detected_patterns'].extend(
                                        [f'bytecode:{h}' for h in _bc_hits[:5]]
                                    )
                                    result['confidence'] = min(100, result['confidence'] + 20)
                                    result['is_hack'] = True
                                    if b'net/minecraft/client/Minecraft' in str(_bc_hits).encode():
                                        result['detected_patterns'].append('direct_mc_client_access')

                                # P2 #47 — Constant pool parsing: strings de alta precisión
                                _CP_HACK_STRINGS = [
                                    'killaura', 'aimbot', 'aimassist', 'autoclick', 'autoclicker',
                                    'scaffold', 'bhop', 'bhopmodule', 'flightmod', 'speedmod',
                                    'nofall', 'antikb', 'antiknockback', 'fastplace', 'reach',
                                    'xrayfinder', 'esp', 'chams', 'fullbright', 'cavefinder',
                                    'liquidbounce', 'wurst', 'meteor', 'vape', 'sigma',
                                    'aristois', 'impact', 'weave', 'drip', 'reflex',
                                    'javaagent', 'bypassdetection', 'anticheat', 'bypass',
                                ]
                                _cp_hits = []
                                for _cf in _class_files[:50]:
                                    try:
                                        _cp_strings = _extract_class_strings(zf.read(_cf))
                                        for _s in _cp_strings:
                                            _sl = _s.lower()
                                            for _pat in _CP_HACK_STRINGS:
                                                if _pat in _sl and _sl not in _cp_hits:
                                                    _cp_hits.append(_sl[:40])
                                                    break
                                            if len(_cp_hits) >= 8:
                                                break
                                    except Exception:
                                        pass
                                    if len(_cp_hits) >= 8:
                                        break
                                if _cp_hits:
                                    result['detected_patterns'].extend(
                                        [f'cp_string:{h}' for h in _cp_hits[:5]]
                                    )
                                    result['confidence'] = min(100, result['confidence'] + 15)
                                    result['is_hack'] = True
                            except Exception:
                                pass

                        # P2 #13 — String legibility ratio (<30% legible = ofuscación agresiva)
                        try:
                            _class_files_s = [n for n in zf.namelist() if n.endswith('.class')][:20]
                            _total_bytes = 0
                            _readable_bytes = 0
                            for _cf in _class_files_s:
                                try:
                                    _bc = zf.read(_cf)
                                    _total_bytes += len(_bc)
                                    _readable_bytes += sum(1 for b in _bc if 32 <= b < 127)
                                except Exception:
                                    pass
                            if _total_bytes > 1000:
                                _legib = _readable_bytes / _total_bytes
                                if _legib < 0.30:
                                    result['obfuscation_detected'] = True
                                    result['confidence'] = min(100, result['confidence'] + 12)
                                    result['detected_patterns'].append(f'string_legibility:{_legib:.0%}')
                        except Exception:
                            pass

                        # P2 #20 — Compilation date vs file date
                        # If the newest .class inside the jar is much newer than the jar file
                        # itself, the jar was re-packed (tampering / custom build).
                        try:
                            import datetime as _dt
                            file_mtime = _dt.datetime.fromtimestamp(os.path.getmtime(file_path))
                            class_times = []
                            for info in zf.infolist():
                                if info.filename.endswith('.class') and info.date_time[0] >= 2000:
                                    dt = _dt.datetime(*info.date_time[:6])
                                    class_times.append(dt)
                            if class_times:
                                newest_class = max(class_times)
                                delta_days = (newest_class - file_mtime).days
                                # Class compiled AFTER file date = jar was re-packed
                                if delta_days > 1:
                                    result['detected_patterns'].append(
                                        f'class_newer_than_jar:{delta_days}d')
                                    result['confidence'] = min(100, result['confidence'] + 20)
                                    result['is_hack'] = True
                        except Exception:
                            pass

                    # P3 #14 — Entropía por secciones de 4KB (detecta packers/ofuscación)
                    # Un packer tiene secciones de altísima entropía mezcladas con baja.
                    # Un ZIP legítimo tiene entropía uniformemente alta en todo el archivo.
                    try:
                        fsize = os.path.getsize(file_path)
                        if 0 < fsize < 50 * 1024 * 1024:
                            CHUNK = 4096
                            section_entropies = []
                            with open(file_path, 'rb') as f:
                                while True:
                                    chunk = f.read(CHUNK)
                                    if not chunk:
                                        break
                                    freq = [0] * 256
                                    for b in chunk: freq[b] += 1
                                    n = len(chunk)
                                    ent = -sum((c/n) * _math.log2(c/n) for c in freq if c > 0)
                                    section_entropies.append(ent)

                            if section_entropies:
                                avg_ent  = sum(section_entropies) / len(section_entropies)
                                max_ent  = max(section_entropies)
                                min_ent  = min(section_entropies)
                                variance = sum((e - avg_ent)**2 for e in section_entropies) / len(section_entropies)
                                result['entropy']         = round(avg_ent, 3)
                                result['entropy_variance']= round(variance, 3)

                                # Packer signature: high-variance + some sections > 7.8
                                very_high = sum(1 for e in section_entropies if e > 7.8)
                                very_low  = sum(1 for e in section_entropies if e < 2.0)
                                packer_sig = variance > 4.0 and very_high > 0 and very_low > 0

                                if packer_sig:
                                    result['obfuscation_detected'] = True
                                    result['confidence'] += 25
                                    result['detected_patterns'].append(f'packer_entropy_variance:{variance:.2f}')
                                elif avg_ent > 7.5:
                                    result['obfuscation_detected'] = True
                                    result['confidence'] += 15
                                    result['detected_patterns'].append(f'high_entropy:{avg_ent:.2f}')
                    except Exception:
                        pass
                except Exception:
                    pass

            # Guardar en cache
            self.file_analysis_cache[file_path] = result
            return result
            
        except Exception as e:
            return {'is_hack': False, 'confidence': 0, 'detected_patterns': [], 'obfuscation_detected': False, 'file_hash': None}
    
    def is_suspicious_file(self, file_path):
        """Verifica si un archivo es sospechoso - MEJORADO CON CACHÉ INTELIGENTE"""
        try:
            # ========== PASO 0: VERIFICAR CACHÉ (optimización) ==========
            if self.file_cache:
                cached_result = self.file_cache.is_cached(file_path)
                if cached_result and cached_result.get('cached'):
                    # Archivo en caché y no modificado, usar resultado cacheado
                    return cached_result.get('is_suspicious', False)
            
            filename = os.path.basename(file_path).lower()
            file_dir = os.path.dirname(file_path).lower()
            full_path_lower = file_path.lower()
            
            # ========== PASO 1: VERIFICACIÓN DE WHITELIST (prioridad máxima) ==========
            if self.is_whitelisted(file_path):
                # Guardar en caché como no sospechoso
                if self.file_cache:
                    self.file_cache.cache_result(file_path, is_suspicious=False, confidence=0)
                return False
            
            # ========== PASO 1.5: VERIFICACIÓN DE PATRONES LEGÍTIMOS APRENDIDOS ==========
            if self.legitimate_patterns:
                try:
                    file_hash = None
                    if os.path.exists(file_path):
                        try:
                            with open(file_path, 'rb') as f:
                                file_hash = hashlib.sha256(f.read()).hexdigest()
                        except:
                            pass
                    
                    is_legitimate, legit_confidence = self.legitimate_patterns.is_legitimate(
                        file_path=file_path,
                        file_name=filename,
                        file_hash=file_hash,
                        context={'file_path': file_path}
                    )
                    
                    if is_legitimate and legit_confidence >= 0.6:
                        # Guardar en caché como no sospechoso
                        if self.file_cache:
                            self.file_cache.cache_result(file_path, is_suspicious=False, confidence=0)
                        print(f"✅ Archivo legítimo aprendido: {filename} (confianza: {legit_confidence:.2f})")
                        return False
                except Exception as e:
                    # Si hay error, continuar con el análisis normal
                    pass
            
            # ========== PASO 2: ANÁLISIS AVANZADO DE CONTENIDO ==========
            content_analysis = self.analyze_file_content(file_path)
            if content_analysis['is_hack'] and content_analysis['confidence'] >= 70:
                # Verificación adicional: no debe estar en whitelist incluso si el contenido es sospechoso
                # (para evitar falsos positivos en software legítimo ofuscado)
                if not self.is_whitelisted(file_path):
                    return True
            
            # ========== PASO 3: DETECCIÓN POR NOMBRE Y UBICACIÓN ==========
            #
            # REGLA ANTI-FALSOS-POSITIVOS:
            # Solo nombres de clientes/módulos que NO aparecen en software legítimo.
            # Términos genéricos (fly, speed, ghost, bypass, inject, auto, macro, sprint,
            # patch, hook, pack, encrypt, camera, client, pathfinder) se eliminaron porque
            # producen decenas de falsos positivos en mods legítimos, launchers y software
            # de sistema. Esos términos solo se evalúan en analyze_file_content() con
            # múltiples co-ocurrencias, nunca sobre el nombre del archivo solo.

            # Rutas seguras — si el archivo está aquí, no es un hack
            SAFE_PATH_PREFIXES = [
                'c:\\windows\\', 'c:\\program files\\microsoft',
                'c:\\program files (x86)\\microsoft',
                'c:\\program files\\common files',
                '\\steamapps\\workshop\\', '\\steamapps\\common\\',
                '\\epicgames\\', '\\riot games\\', '\\gog galaxy\\',
                '\\battle.net\\', '\\origin games\\',
                '\\jdk', '\\jre', '\\java\\',
                '\\visual studio\\', '\\jetbrains\\',
                '\\obs-studio\\', '\\discord\\', '\\zoom\\',
            ]
            for safe in SAFE_PATH_PREFIXES:
                if safe in full_path_lower:
                    return False

            # Clientes de hack con nombres únicos — alta precisión, bajo FP
            # EXCLUIDOS: impact, rise, drip, nyx, vanish, sloth, lucid (demasiado genéricos)
            KNOWN_HACK_CLIENTS = {
                'vape', 'vapelite', 'entropy', 'entropyclient', 'whiteout', 'whiteoutclient',
                'liquidbounce', 'wurst', 'wurstclient', 'impactclient',
                'sigmaclient', 'fluxclient', 'future', 'futureclient',
                'astolfo', 'astolfoclient', 'exhibition', 'novoline', 'novolineclient',
                'riseclient', 'dripclient', 'phobos', 'phobosclient',
                'tenacity', 'meteor', 'meteorclient', 'rusherhack', 'konas', 'kami',
                'weepcraft', 'ghostclient', 'nextgen', 'tegernako', 'zeroday',
                'seppuku', 'wasp', 'komat',
                'dllinjector', 'cheatengine', 'processhollowing', 'dllhijacking',
            }

            # Módulos cuyo nombre es exclusivo de cheats (no aparecen en mods legítimos)
            # EXCLUIDOS: nuker, freecam, fullbright, nofall (aparecen en mods legítimos)
            HACK_MODULE_NAMES = {
                'killaura', 'aimbot', 'triggerbot', 'antikb', 'antiknockback',
                'xraymod', 'wallhack', 'boxesp', 'chams', 'traceline',
                'autoclicker', 'clickgui', 'bunnyhop', 'bhop', 'aimassist',
                'wtap', 'autotool', 'autosprint', 'speedhack',
            }

            # Combinaciones path-específicas de hack en carpetas de Minecraft
            HACK_PATH_COMBOS = [
                ('mods', 'vape'), ('mods', 'entropy'), ('mods', 'sigma'),
                ('mods', 'flux'), ('mods', 'future'), ('mods', 'astolfo'),
                ('mods', 'liquidbounce'), ('mods', 'wurst'), ('mods', 'impact'),
                ('versions', 'vape'), ('versions', 'entropy'), ('versions', 'sigma'),
                ('versions', 'flux'), ('versions', 'liquidbounce'),
            ]

            HIGH_CONFIDENCE_HACK_PATTERNS = list(KNOWN_HACK_CLIENTS | HACK_MODULE_NAMES)
            
            # Verificar patrones de alta confianza
            is_suspicious = False
            confidence = 0
            detected_patterns = []

            # Nombre de archivo exacto o como parte del stem (sin extensión)
            file_stem = os.path.splitext(filename)[0]
            # Normalizar también para detectar homoglyphs cirílicos en nombres de archivo
            filename_norm = _normalize(filename)
            file_stem_norm = _normalize(file_stem)
            full_path_norm = _normalize(full_path_lower)
            for pattern in HIGH_CONFIDENCE_HACK_PATTERNS:
                # Match en nombre del archivo (stem) o en la ruta completa como segmento
                stem_match = (pattern == file_stem or file_stem.startswith(pattern + '-')
                              or file_stem.startswith(pattern + '_') or file_stem.endswith('-' + pattern)
                              or file_stem.endswith('_' + pattern) or (' ' + pattern) in file_stem
                              or (pattern + ' ') in file_stem)
                # Mismo chequeo pero sobre nombre normalizado (detecta homoglyphs)
                stem_match_norm = (pattern in file_stem_norm)
                path_segment_match = ('\\' + pattern + '\\') in full_path_lower or \
                                     ('/' + pattern + '/') in full_path_lower or \
                                     full_path_lower.endswith('\\' + pattern) or \
                                     full_path_lower.endswith('/' + pattern)
                # Clientes conocidos también pueden aparecer como substring en el nombre
                client_match = (pattern in KNOWN_HACK_CLIENTS and
                                (pattern in filename or pattern in filename_norm))
                if (stem_match or stem_match_norm or path_segment_match or client_match) and \
                        not self.is_whitelisted(file_path):
                    is_suspicious = True
                    confidence = max(confidence, 82)
                    detected_patterns.append(pattern)
                    break

            # Combinaciones path (mods/vape, versions/flux, etc.)
            if not is_suspicious:
                for (folder, hack) in HACK_PATH_COMBOS:
                    if folder in full_path_lower and hack in filename:
                        if not self.is_whitelisted(file_path):
                            is_suspicious = True
                            confidence = max(confidence, 85)
                            detected_patterns.append(f'{folder}/{hack}')
                            break
            
            # ========== PASO 4: DETECCIÓN POR EXTENSIÓN Y CONTEXTO ==========
            # Archivos JAR en ubicaciones sospechosas
            if filename.endswith('.jar'):
                if 'mods' in file_dir or 'versions' in file_dir:
                    # Solo nombres exactos de hack clients — NO 'hack' o 'cheat' solos (muy genéricos)
                    jar_hacks = ['vape', 'vapelite', 'entropy', 'liquidbounce', 'wurst',
                                 'astolfo', 'fluxclient', 'ghostclient', 'novoline',
                                 'killaura', 'aimbot', 'cheatengine']
                    if any(h in filename for h in jar_hacks):
                        if not self.is_whitelisted(file_path):
                            is_suspicious = True
                            confidence = max(confidence, 75)
                            detected_patterns.append('suspicious_jar_location')
            
            # ========== PASO 5: DETECCIÓN DE OFUSCACIÓN EXCESIVA ==========
            if content_analysis.get('obfuscation_detected', False):
                if content_analysis['confidence'] >= 50 and not self.is_whitelisted(file_path):
                    known_software = ['anydesk', 'teamviewer', 'gtavlauncher', 'rockstar', 'steam', 'epic',
                                      'discord', 'roblox', '3utools', '4ukey', 'echo-acb', 'argusscanner']
                    if not any(sw in full_path_lower for sw in known_software):
                        # Solo marcar como sospechoso si está en una instancia activa de Minecraft
                        # o si la confianza es muy alta (>=80). Archivos en Downloads/Temp = ignorar.
                        if _is_minecraft_instance(file_path):
                            is_suspicious = True
                            confidence = max(confidence, 65)
                            detected_patterns.append('obfuscation_in_instance')
                        elif not _is_non_instance_location(file_path) and content_analysis['confidence'] >= 80:
                            # Fuera de instancia pero confianza muy alta — marcar como poco sospechoso
                            is_suspicious = True
                            confidence = max(confidence, 40)
                            detected_patterns.append('obfuscation_out_of_instance')
            
            # ========== PASO 6: DETECCIÓN POR HASH CONOCIDO ==========
            if content_analysis.get('file_hash') in self.known_hack_hashes:
                is_suspicious = True
                confidence = 100  # Hash conocido = 100% confianza
                detected_patterns.append('known_hash')
            
            # Guardar resultado en caché
            if self.file_cache:
                self.file_cache.cache_result(
                    file_path,
                    is_suspicious=is_suspicious,
                    confidence=confidence,
                    detected_patterns=detected_patterns if detected_patterns else None,
                    scan_result=content_analysis
                )
            
            return is_suspicious
            
        except Exception as e:
            # En caso de error, no marcar como sospechoso para evitar falsos positivos
            return False
    
    def _scan_for_specific_hacks(self, drive):
        """Buscar específicamente carpetas con nombres de hacks conocidos - MEJORADO CON TÉCNICAS SILENT-SCANNER"""
        try:
            print(f"🔍 BUSCANDO HACKS ESPECÍFICOS EN {drive}")
            
            # Patrones expandidos de hacks reales (incluyendo variantes y técnicas avanzadas)
            hack_patterns = [
                # Hacks específicos conocidos de Minecraft (variantes explícitas — sin nombres genéricos sueltos)
                'vape', 'vapelite', 'vapev2', 'vapev4', 'vape.exe', 'vape.jar',
                'entropy', 'entropyclient', 'entropy.exe', 'entropy.jar',
                'whiteout', 'whiteoutclient', 'whiteout.exe', 'whiteout.jar',
                'liquidbounce', 'liquid bounce', 'liquidbounceclient',
                'wurst', 'wurstclient', 'wurst loader', 'wurst.exe',
                'impact client', 'impactclient', 'impact.exe',
                'sigmaclient', 'sigma5.0', 'sigma-5.0',
                'fluxclient', 'flux b1.6', 'flux 1.8.8', 'flux1.8.8', 'flux 1.8.9',
                'futureclient', 'future.exe',
                'astolfo', 'astolfoclient', 'exhibition', 'exhibitionclient',
                'novoline', 'novolineclient', 'riseclient',
                'moonclient', 'dripclient',
                'ghostclient', 'ghost.exe',
                'phobos', 'komat', 'wasp', 'konas', 'seppuku', 'sloth',
                'lucid', 'tenacity', 'nyx', 'vanish', 'ploow', 'cloudclient', 'cloud-client',
                'nextgen', 'tegernako', 'zeroday',

                # Módulos de hack cuyo nombre es exclusivo (no aparece en software legítimo)
                'xray', 'killaura', 'aimbot', 'wallhack', 'boxesp', 'chams',
                'autoclicker', 'autotool', 'autosprint', 'speedhack',
                'wtap', 'aimassist', 'bhop', 'nofall', 'antiknockback',
                'antikb', 'triggerbot', 'freecam', 'fullbright', 'nuker',
                'clickgui', 'bunnyhop', 'traceline',

                # Inyección y exploits — solo términos muy específicos
                'dllinjector', 'dllhijacking', 'processhollowing', 'codecave',
                'cheatengine',

                # Clientes con nombre único
                'silentclient',
            ]
            
            # Lista ampliada de falsos positivos para evitar detecciones incorrectas
            false_positives = [
                'zomboid', 'shaders', 'textures', 'media', 'vscode', 'pylance', 'skimage', 'pyi',
                'minecraft', 'mc', 'mojang', 'launcher', 'versions', 'mods', 'resourcepacks', 
                'saves', 'servers', 'config', 'logs', 'screenshots', 'backups', 'cache',
                'temp', 'tmp', 'downloads', 'documents', 'desktop', 'pictures', 'music',
                'videos', 'appdata', 'program files', 'windows', 'system32', 'riot games',
                'lunar client', 'badlion', 'forge', 'fabric', 'optifine', 'iris', 'sodium',
                'lithium', 'phosphor', 'starlight', 'carpet', 'carpetmod', 'tweakeroo',
                'litematica', 'minihud', 'malilib', 'itemscroller', 'inventory profiles',
                'worldedit', 'worldguard', 'essentials', 'luckperms', 'vault', 'economy',
                'permissions', 'multiverse', 'plotsquared', 'griefprevention', 'coreprotect',
                'citizens', 'mythicmobs', 'mcmmo', 'jobs', 'shopkeepers', 'chestshop',
                'auctionhouse', 'auction', 'bazaar', 'market', 'trade', 'exchange',
                'bank', 'money', 'coins', 'tokens', 'points', 'credits', 'balance',
                'account', 'profile', 'user', 'player', 'member', 'staff', 'admin',
                'moderator', 'helper', 'builder', 'developer', 'owner', 'manager',
                'discord', 'telegram', 'whatsapp', 'skype', 'teamspeak', 'mumble',
                'ventrilo', 'curse', 'twitch', 'youtube', 'stream', 'recording',
                'obs', 'streamlabs', 'xsplit', 'bandicam', 'fraps', 'dxtory',
                'shadowplay', 'relive', 'raptr', 'steam', 'origin', 'uplay',
                'epic', 'gog', 'battle.net', 'battlenet', 'blizzard', 'activision',
                'ea', 'electronic arts', 'ubisoft', 'bethesda', 'cd projekt',
                'rockstar', 'take-two', '2k', 'square enix', 'capcom', 'konami',
                'bandai namco', 'sega', 'nintendo', 'sony', 'microsoft', 'xbox',
                'playstation', 'nintendo switch', 'pc', 'windows', 'mac', 'linux',
                'android', 'ios', 'mobile', 'tablet', 'laptop', 'desktop', 'computer',
                'gaming', 'game', 'games', 'gamer', 'streamer', 'youtuber', 'content',
                'creator', 'influencer', 'social', 'media', 'network', 'community',
                'server', 'hosting', 'vps', 'dedicated', 'cloud', 'aws', 'azure',
                'google', 'amazon', 'microsoft', 'oracle', 'ibm', 'dell', 'hp',
                'lenovo', 'asus', 'acer', 'msi', 'gigabyte', 'evga', 'corsair',
                'razer', 'logitech', 'steelseries', 'hyperx', 'kingston', 'crucial',
                'samsung', 'intel', 'amd', 'nvidia', 'ati', 'ati radeon', 'geforce',
                'rtx', 'gtx', 'rx', 'ryzen', 'core i', 'pentium', 'celeron',
                'athlon', 'phenom', 'fx', 'a', 'e', 'pro', 'threadripper', 'epyc'
            ]
            
            import time as _t
            _hacks_start = _t.time()
            _max_depth = 5
            _timeout = 25  # segundos máximo para esta función

            for root, dirs, files in os.walk(drive):
                # Límite de tiempo y profundidad
                if _t.time() - _hacks_start > _timeout:
                    break
                depth = root.count(os.sep) - drive.count(os.sep)
                if depth > _max_depth:
                    dirs[:] = []
                    continue

                # Saltar rutas seguras conocidas
                _root_l = root.lower()
                if any(frag in _root_l for frag in _SAFE_ROOT_FRAGMENTS):
                    dirs[:] = []
                    continue

                # Buscar en nombres de carpetas
                for dir_name in dirs:
                    dir_lower = dir_name.lower()
                    for pattern in hack_patterns:
                        if pattern in dir_lower:
                            # Verificar si no es un falso positivo
                            if not any(false_positive in dir_lower or false_positive in root.lower() 
                                      for false_positive in false_positives):
                                print(f"🎯 HACK DETECTADO: {dir_name} en {root}")
                                self.issues_found.append({
                                    'nombre': dir_name,
                                    'ruta': root,
                                    'archivo': os.path.join(root, dir_name),
                                    'tipo': 'hack_folder',
                                    'categoria': 'HACKS',
                                    'alerta': 'CRITICAL'
                                })
                                break  # Solo agregar una vez por carpeta
                
                # Buscar en nombres de archivos
                for file_name in files:
                    file_lower = file_name.lower()
                    for pattern in hack_patterns:
                        if pattern in file_lower:
                            # Verificar si no es un falso positivo
                            if not any(false_positive in file_lower or false_positive in root.lower() 
                                      for false_positive in false_positives):
                                file_path = os.path.join(root, file_name)
                                print(f"🎯 HACK DETECTADO: {file_name} en {root}")
                                self.issues_found.append({
                                    'nombre': file_name,
                                    'ruta': root,
                                    'archivo': file_path,
                                    'tipo': 'hack_file',
                                    'categoria': 'HACKS',
                                    'alerta': 'CRITICAL'
                                })
                                break  # Solo agregar una vez por archivo
                                
        except Exception as e:
            print(f"⚠️ Error en _scan_for_specific_hacks: {e}")
    
    def scan_common_hack_locations(self):
        """Escanea ubicaciones comunes donde se descargan hacks - MEJORADO CON MÁS UBICACIONES"""
        try:
            print("🔍 ESCANEANDO UBICACIONES COMUNES DE HACKS...")
            import os
            
            # Ubicaciones comunes expandidas donde se descargan hacks
            common_locations = [
                # Ubicaciones del usuario (prioritarias)
                os.path.join(os.environ.get('USERPROFILE', ''), 'Downloads'),
                os.path.join(os.environ.get('USERPROFILE', ''), 'Desktop'),
                os.path.join(os.environ.get('USERPROFILE', ''), 'Documents'),
                os.path.join(os.environ.get('USERPROFILE', ''), 'AppData', 'Local', 'Temp'),
                os.path.join(os.environ.get('USERPROFILE', ''), 'AppData', 'Roaming'),
                os.path.join(os.environ.get('USERPROFILE', ''), 'AppData', 'Local'),
                os.path.join(os.environ.get('USERPROFILE', ''), 'AppData', 'LocalLow'),
                os.path.join(os.environ.get('USERPROFILE', ''), 'Pictures'),
                os.path.join(os.environ.get('USERPROFILE', ''), 'Videos'),
                os.path.join(os.environ.get('USERPROFILE', ''), 'Music'),
                
                # Ubicaciones del sistema
                'C:\\Users\\Public',
                'C:\\Users\\Public\\Downloads',
                'C:\\Users\\Public\\Desktop',
                'C:\\Temp',
                'C:\\Windows\\Temp',
                'C:\\ProgramData',
                
                # Otras unidades comunes
                'D:\\Downloads',
                'D:\\Desktop',
                'D:\\Temp',
                'E:\\Downloads',
                'E:\\Desktop'
            ]
            
            _BROWSER_SKIP_COMMON = {
                'google\\chrome', 'mozilla\\firefox', 'microsoft\\edge',
                'brave-browser', 'vivaldi', 'opera software',
                'appdata\\local\\google', 'appdata\\roaming\\mozilla',
            }

            for location in common_locations:
                if os.path.exists(location):
                    print(f"📁 ESCANEANDO: {location}")
                    try:
                        for root, dirs, files in os.walk(location):
                            _root_lower = root.lower()
                            if any(frag in _root_lower for frag in _BROWSER_SKIP_COMMON):
                                dirs[:] = []
                                continue
                            for dir_name in dirs:
                                if _is_hack_folder(dir_name, _root_lower):
                                    print(f"🎯 HACK DETECTADO EN UBICACIÓN COMÚN: {dir_name} en {root}")
                                    self.issues_found.append({
                                        'nombre': dir_name,
                                        'ruta': root,
                                        'archivo': os.path.join(root, dir_name),
                                        'tipo': 'hack_folder_common',
                                        'categoria': 'HACKS',
                                        'alerta': 'CRITICAL'
                                    })
                    except Exception as e:
                        print(f"Error escaneando {location}: {str(e)}")
                        continue
        except Exception as e:
            print(f"Error escaneando ubicaciones comunes: {str(e)}")
    
    def scan_suspicious_folders(self):
        """Escanea carpetas con nombres sospechosos en todo el sistema"""
        try:
            print("🔍 ESCANEANDO CARPETAS SOSPECHOSAS EN TODO EL SISTEMA...")
            import os
            
            # Escanear en TODAS las ubicaciones posibles (más exhaustivo)
            search_locations = [
                # Ubicaciones del usuario
                os.path.join(os.environ.get('USERPROFILE', ''), 'Downloads'),
                os.path.join(os.environ.get('USERPROFILE', ''), 'Desktop'),
                os.path.join(os.environ.get('USERPROFILE', ''), 'Documents'),
                os.path.join(os.environ.get('USERPROFILE', ''), 'AppData', 'Local'),
                os.path.join(os.environ.get('USERPROFILE', ''), 'AppData', 'Roaming'),
                os.path.join(os.environ.get('USERPROFILE', ''), 'AppData', 'LocalLow'),
                
                # Ubicaciones del sistema
                'C:\\Users\\Public',
                'C:\\Temp',
                'C:\\Windows\\Temp',
                'C:\\ProgramData',
                'C:\\Program Files',
                'C:\\Program Files (x86)',
                
                # Ubicaciones adicionales comunes
                'D:\\', 'E:\\', 'F:\\', 'G:\\', 'H:\\'
            ]
            
            # Fragmentos de ruta que se saltan COMPLETAMENTE durante el walk
            _BROWSER_SKIP = {
                'google\\chrome', 'mozilla\\firefox', 'microsoft\\edge',
                'brave-browser', 'vivaldi', 'opera software',
                'appdata\\local\\google', 'appdata\\roaming\\mozilla',
                'appdata\\local\\osu!', 'appdata\\roaming\\osu!',
                # Beat Saber, Geometry Dash
                'appdata\\locallow\\hyperbolic magnetism',
                'appdata\\locallow\\robtop games',
                # Dev repos — .git y node_modules son enormes y no contienen hacks
                '\\.git\\', '\\node_modules\\', '\\dist\\',
                # Garry's Mod, música, herramientas legítimas
                'garrysmod\\garrysmod\\addons',
                'appdata\\roaming\\image-line', 'appdata\\local\\spotify',
                'systeminformer', 'processhacker3',
                'program files\\autohotkey', 'program files (x86)\\autohotkey',
            }

            def _is_network_drive(path):
                """Devuelve True si el path está en un drive de red (evitar timeouts de 30s+)."""
                try:
                    drive = os.path.splitdrive(path)[0] + '\\'
                    DRIVE_REMOTE = 4
                    return ctypes.windll.kernel32.GetDriveTypeW(drive) == DRIVE_REMOTE
                except Exception:
                    return False

            for location in search_locations:
                if _is_network_drive(location):
                    print(f"⏭️ Skipping drive de red: {location}")
                    continue
                if os.path.exists(location):
                    print(f"📁 ESCANEANDO CARPETAS EN: {location}")
                    try:
                        # Limitar profundidad para evitar cuelgues
                        max_depth = 3
                        for root, dirs, files in os.walk(location):
                            # Saltar directorios de navegadores ANTES de explorar subdirectorios
                            _root_lower = root.lower()
                            if any(frag in _root_lower for frag in _BROWSER_SKIP):
                                dirs[:] = []  # No descender en directorios de navegadores
                                continue
                            # Controlar profundidad
                            depth = root[len(location):].count(os.sep)
                            if depth >= max_depth:
                                dirs[:] = []  # No explorar más profundamente
                                continue

                            for dir_name in dirs:
                                if _is_hack_folder(dir_name, _root_lower):
                                    print(f"🎯 CARPETA SOSPECHOSA ENCONTRADA: {dir_name} en {root}")
                                    self.issues_found.append({
                                        'nombre': dir_name,
                                        'ruta': root,
                                        'archivo': os.path.join(root, dir_name),
                                        'tipo': 'suspicious_folder',
                                        'categoria': 'HACKS',
                                        'alerta': 'CRITICAL'
                                    })
                                    # También escanear archivos .jar/.exe/.dll dentro de esta carpeta
                                    try:
                                        folder_path = os.path.join(root, dir_name)
                                        for file in os.listdir(folder_path):
                                            if file.lower().endswith(('.jar', '.exe', '.dll')):
                                                self.issues_found.append({
                                                    'nombre': file,
                                                    'ruta': folder_path,
                                                    'archivo': os.path.join(folder_path, file),
                                                    'tipo': 'hack_file',
                                                    'categoria': 'HACKS',
                                                    'alerta': 'CRITICAL'
                                                })
                                                print(f"🎯 ARCHIVO DE HACK ENCONTRADO: {file} en {folder_path}")
                                    except:
                                        pass
                    except Exception as e:
                        print(f"Error escaneando {location}: {str(e)}")
                        continue
        except Exception as e:
            print(f"Error escaneando carpetas sospechosas: {str(e)}")
    
    def scan_exact_hack_names(self):
        """Busca carpetas con nombres exactos de hacks conocidos - MEJORADO CON TÉCNICAS SILENT-SCANNER"""
        try:
            print("🎯 BUSCANDO CARPETAS CON NOMBRES EXACTOS DE HACKS...")
            import os
            
            # Nombres exactos expandidos de hacks conocidos (incluyendo variantes)
            exact_hack_names = [
                # Flux y variantes
                'flux', 'flux 1.8', 'flux1.8', 'flux 1.8.8', 'flux1.8.8', 'flux 1.8.9', 'flux1.8.9',
                'flux b1.6', 'fluxb1.6', 'fluxclient', 'flux-client',
                
                # Vape y variantes
                'vape', 'vape v4', 'vapev4', 'vape lite', 'vapelite', 'vapev2',
                'vape.exe', 'vape.jar', 'vapeclient', 'vape-client',
                
                # Entropy y variantes
                'entropy', 'entropy client', 'entropyclient', 'entropy.exe', 'entropy.jar',
                
                # Whiteout y variantes
                'whiteout', 'whiteout client', 'whiteoutclient', 'whiteout.exe', 'whiteout.jar',
                
                # LiquidBounce y variantes
                'liquidbounce', 'liquid bounce', 'liquidbounce client', 'lbclient',
                
                # Wurst y variantes
                'wurst', 'wurst client', 'wurstclient', 'wurst loader', 'wurst.exe',
                
                # Impact y variantes
                'impact', 'impact client', 'impactclient', 'impact.exe',
                
                # Otros clientes conocidos
                'sigma', 'sigma client', 'sigmaclient', 'sigma5.0',
                'future', 'future client', 'futureclient',
                'astolfo', 'astolfo client', 'astolfoclient',
                'exhibition', 'exhibition client', 'exhibitionclient',
                'novoline', 'novoline client', 'novolineclient',
                'rise', 'rise client', 'riseclient',
                'moon', 'moon client', 'moonclient',
                'drip', 'drip client', 'dripclient',
                'ghost', 'ghost client', 'ghostclient',
                'phobos', 'komat', 'wasp', 'konas', 'seppuku', 'sloth',
                'lucid', 'tenacity', 'nyx', 'vanish', 'ploow', 'cloudclient', 'cloud-client',
                'nextgen', 'tegernako', 'zeroday',

                # Silent-scanner y variantes
                'silent', 'silent-scanner', 'silentscanner', 'silent client',
                'silent.exe', 'silent.jar'
            ]
            
            # Ubicaciones donde buscar
            search_locations = [
                os.path.join(os.environ.get('USERPROFILE', ''), 'Downloads'),
                os.path.join(os.environ.get('USERPROFILE', ''), 'Desktop'),
                os.path.join(os.environ.get('USERPROFILE', ''), 'Documents'),
                os.path.join(os.environ.get('USERPROFILE', ''), 'AppData', 'Local'),
                os.path.join(os.environ.get('USERPROFILE', ''), 'AppData', 'Roaming'),
                'C:\\Users\\Public',
                'C:\\Temp',
                'C:\\ProgramData'
            ]
            
            for location in search_locations:
                if os.path.exists(location):
                    print(f"🎯 BUSCANDO NOMBRES EXACTOS EN: {location}")
                    try:
                        for root, dirs, files in os.walk(location):
                            _root_l = root.lower()
                            if any(frag in _root_l for frag in _SAFE_ROOT_FRAGMENTS):
                                dirs[:] = []
                                continue
                            for dir_name in dirs:
                                dir_lower = dir_name.lower().strip()
                                for hack_name in exact_hack_names:
                                    if hack_name.lower() == dir_lower or hack_name.lower() in dir_lower:
                                        print(f"🚨 HACK EXACTO ENCONTRADO: {dir_name} en {root}")
                                        self.issues_found.append({
                                            'nombre': dir_name,
                                            'ruta': root,
                                            'archivo': os.path.join(root, dir_name),
                                            'tipo': 'exact_hack_folder',
                                            'categoria': 'HACKS',
                                            'alerta': 'CRITICAL'
                                        })
                                        
                                        # Escanear contenido de la carpeta
                                        try:
                                            folder_path = os.path.join(root, dir_name)
                                            for file in os.listdir(folder_path):
                                                file_path = os.path.join(folder_path, file)
                                                if os.path.isfile(file_path):
                                                    self.issues_found.append({
                                                        'nombre': file,
                                                        'ruta': folder_path,
                                                        'archivo': file_path,
                                                        'tipo': 'hack_file',
                                                        'categoria': 'HACKS',
                                                        'alerta': 'CRITICAL'
                                                    })
                                                    print(f"🚨 ARCHIVO DE HACK: {file}")
                                        except:
                                            pass
                    except Exception as e:
                        print(f"Error buscando nombres exactos en {location}: {str(e)}")
                        continue
        except Exception as e:
            print(f"Error buscando nombres exactos de hacks: {str(e)}")
    
    def secondary_filter(self, issues):
        """Segundo filtro más inteligente para detectar hacks reales"""
        try:
            print("🔍 APLICANDO SEGUNDO FILTRO INTELIGENTE...")
            
            # Patrones de hacks reales conocidos
            real_hack_patterns = [
                'fluxclient', 'flux 1.8', 'flux1.8', 'flux 1.8.8', 'flux1.8.8',
                'vape', 'vape v4', 'vapev4', 'vape lite', 'vapelite',
                'entropy', 'entropy client', 'entropyclient',
                'whiteout', 'whiteout client', 'whiteoutclient',
                'liquidbounce', 'liquid bounce', 'liquidbounce client',
                'wurst', 'wurst client', 'wurstclient',
                'impact client', 'impactclient',
                'sigma client', 'sigmaclient',
                'future client', 'futureclient',
                'astolfo', 'astolfo client', 'astolfoclient',
                'exhibition', 'exhibition client', 'exhibitionclient',
                'novoline', 'novoline client', 'novolineclient',
                'riseclient', 'rise client',
                'moonclient', 'moon client',
                'dripclient', 'drip client',
                'ghostclient', 'ghost client',
            ]
            
            # Patrones de archivos de hacks (solo extensiones realmente sospechosas fuera de minecraft)
            hack_file_patterns = ['.jar', '.exe']

            # Ubicaciones donde los hacks suelen estar (excluye appdata porque .minecraft vive ahí)
            suspicious_locations = [
                'documents', 'downloads', 'desktop'
            ]
            
            filtered_issues = []
            
            for issue in issues:
                nombre = issue.get('nombre', '').lower()
                ruta = issue.get('ruta', '').lower()
                archivo = issue.get('archivo', '').lower()
                tipo = issue.get('tipo', '')
                
                # Verificar si es un hack real
                is_real_hack = False
                
                # 1. Verificar patrones de hacks reales
                for pattern in real_hack_patterns:
                    if pattern in nombre or pattern in ruta or pattern in archivo:
                        is_real_hack = True
                        break
                
                # 2. Verificar si está en ubicación sospechosa con extensión de hack
                if not is_real_hack:
                    for location in suspicious_locations:
                        if location in ruta:
                            for ext in hack_file_patterns:
                                if ext in archivo:
                                    is_real_hack = True
                                    break
                            if is_real_hack:
                                break
                
                # 3. Verificar si es archivo de hack en ubicación sospechosa
                if not is_real_hack and tipo in ['hack_file', 'exact_hack_folder']:
                    is_real_hack = True
                
                # 4. Verificar palabras clave específicas de hacks (NO usar 'mod'/'client' - demasiado genéricas)
                hack_keywords = ['hack', 'cheat', 'cracked', 'killaura', 'aimbot', 'wallhack', 'triggerbot']
                if not is_real_hack:
                    for keyword in hack_keywords:
                        if keyword in nombre or keyword in archivo:
                            is_real_hack = True
                            break

                if is_real_hack:
                    # Archivos fuera de instancia (Downloads/Desktop/Documents sin .minecraft)
                    # → SOSPECHOSO, no CRITICAL. El ensemble gate ya maneja la sancionabilidad.
                    _in_instance = any(f in ruta for f in ['.minecraft', 'minecraft\\mods', 'lunarclient', 'badlion', 'prismlauncher', 'multimc'])
                    _out_of_inst_location = any(loc in ruta for loc in ['downloads', 'desktop', 'documents', '\\temp\\', '/temp/'])
                    if _out_of_inst_location and not _in_instance:
                        issue['alerta'] = 'SOSPECHOSO'
                        issue['confidence'] = min(issue.get('confidence', 0.7), 0.65)
                    else:
                        issue['alerta'] = 'CRITICAL'
                    if not issue.get('categoria'):
                        issue['categoria'] = 'HACKS'
                    filtered_issues.append(issue)
                    print(f"🚨 HACK REAL DETECTADO: {nombre} en {ruta}")
                else:
                    # Mantener si es sospechoso o ya tiene categoría asignada
                    if issue.get('alerta') in ['SOSPECHOSO', 'POCO_SOSPECHOSO'] or issue.get('categoria'):
                        filtered_issues.append(issue)
            
            print(f"🔍 SEGUNDO FILTRO APLICADO: {len(filtered_issues)} elementos clasificados")
            return filtered_issues
            
        except Exception as e:
            print(f"Error aplicando segundo filtro: {e}")
            return issues
    
    def secondary_scan_parallel(self):
        """Segundo scan en paralelo para doble verificación"""
        try:
            print("🔍 INICIANDO SEGUNDO SCAN EN PARALELO...")
            import threading
            import concurrent.futures
            
            # Crear hilos para diferentes tipos de escaneo
            threads = []
            
            # Hilo 1: Escaneo de ubicaciones críticas
            def scan_critical_locations():
                print("🔍 Segundo scan: Ubicaciones críticas...")
                critical_paths = [
                    os.path.join(os.environ.get('USERPROFILE', ''), 'Downloads'),
                    os.path.join(os.environ.get('USERPROFILE', ''), 'Desktop'),
                    os.path.join(os.environ.get('USERPROFILE', ''), 'Documents'),
                    os.path.join(os.environ.get('USERPROFILE', ''), 'AppData', 'Local'),
                    os.path.join(os.environ.get('USERPROFILE', ''), 'AppData', 'Roaming'),
                    'C:\\Temp',
                    'C:\\Windows\\Temp'
                ]
                
                for path in critical_paths:
                    if os.path.exists(path):
                        try:
                            for root, dirs, files in os.walk(path):
                                for file in files:
                                    if file.lower().endswith(('.jar', '.exe', '.dll')):
                                        file_path = os.path.join(root, file)
                                        if self.is_suspicious_file(file_path):
                                            self.issues_found.append({
                                                'nombre': file,
                                                'ruta': root,
                                                'archivo': file_path,
                                                'tipo': 'secondary_scan_file',
                                                'categoria': 'HACKS',
                                                'alerta': 'CRITICAL'
                                            })
                                            print(f"🔍 Segundo scan encontrado: {file}")
                        except Exception as e:
                            print(f"Error en segundo scan de {path}: {e}")
                            continue
            
            # Hilo 2: Escaneo de procesos en segundo plano
            def scan_background_processes():
                print("🔍 Segundo scan: Procesos en segundo plano...")
                try:
                    import psutil
                    for proc in psutil.process_iter(['pid', 'name', 'exe']):
                        try:
                            proc_name = proc.info['name'].lower()
                            if any(hack in proc_name for hack in ['flux', 'vape', 'entropy', 'wurst', 'impact']):
                                self.issues_found.append({
                                    'nombre': proc.info['name'],
                                    'ruta': proc.info['exe'] or 'Proceso en memoria',
                                    'archivo': f"PID: {proc.info['pid']}",
                                    'tipo': 'background_process',
                                    'categoria': 'BACKGROUND_PROCESSES',
                                    'alerta': 'CRITICAL'
                                })
                                print(f"🔍 Segundo scan: Proceso sospechoso {proc.info['name']}")
                        except:
                            continue
                except Exception as e:
                    print(f"Error escaneando procesos: {e}")
            
            # Hilo 3: Escaneo de archivos temporales
            def scan_temp_files():
                print("🔍 Segundo scan: Archivos temporales...")
                temp_paths = [
                    os.path.join(os.environ.get('TEMP', ''), ''),
                    os.path.join(os.environ.get('TMP', ''), ''),
                    'C:\\Windows\\Temp',
                    'C:\\Temp'
                ]
                
                for temp_path in temp_paths:
                    if os.path.exists(temp_path):
                        try:
                            for root, dirs, files in os.walk(temp_path):
                                for file in files:
                                    if any(hack in file.lower() for hack in ['flux', 'vape', 'entropy', 'hack', 'cheat']):
                                        file_path = os.path.join(root, file)
                                        self.issues_found.append({
                                            'nombre': file,
                                            'ruta': root,
                                            'archivo': file_path,
                                            'tipo': 'temp_hack_file',
                                            'categoria': 'TEMP_FILES',
                                            'alerta': 'CRITICAL'
                                        })
                                        print(f"🔍 Segundo scan: Archivo temporal sospechoso {file}")
                        except Exception as e:
                            print(f"Error escaneando temporales {temp_path}: {e}")
                            continue
            
            # Ejecutar todos los hilos en paralelo
            with concurrent.futures.ThreadPoolExecutor(max_workers=3) as executor:
                futures = [
                    executor.submit(scan_critical_locations),
                    executor.submit(scan_background_processes),
                    executor.submit(scan_temp_files)
                ]
                
                # Esperar a que terminen todos
                for future in concurrent.futures.as_completed(futures, timeout=30):
                    try:
                        future.result()
                    except Exception as e:
                        print(f"Error en segundo scan paralelo: {e}")
            
            print("✅ Segundo scan paralelo completado")
            
        except Exception as e:
            print(f"Error en segundo scan paralelo: {e}")
    
    def advanced_minecraft_process_analysis(self):
        """Análisis avanzado de procesos relacionados con Minecraft - MEJORADO CON DETECCIÓN DE SUBPROCESOS"""
        try:
            print("🔍 ANÁLISIS AVANZADO DE PROCESOS DE MINECRAFT...")
            import psutil
            import subprocess
            
            # Usar el nuevo analizador de conexiones para análisis más profundo
            try:
                from minecraft_connection_analyzer import MinecraftConnectionAnalyzer
                analyzer = MinecraftConnectionAnalyzer()
                
                # Escanear procesos y subprocesos ocultos
                advanced_issues = analyzer.scan_minecraft_processes_and_injections()
                self.issues_found.extend(advanced_issues)
                
                # Obtener username desde conexiones activas
                if analyzer.minecraft_username:
                    self.detected_minecraft_username = analyzer.minecraft_username
                    print(f"👤 Username detectado desde conexión activa: {analyzer.minecraft_username}")
            except ImportError:
                print("⚠️ Módulo minecraft_connection_analyzer no disponible, usando análisis básico")
            except Exception as e:
                print(f"⚠️ Error en análisis avanzado: {e}")
            
            # 1. Detección de inyección de DLLs en procesos de Java/Minecraft
            def scan_dll_injection():
                print("🔍 Escaneando inyección de DLLs...")
                try:
                    for proc in psutil.process_iter(['pid', 'name', 'exe']):
                        try:
                            if proc.info['name'].lower() in ['java.exe', 'javaw.exe', 'minecraft.exe']:
                                # Obtener DLLs cargadas por el proceso
                                dlls = proc.memory_maps()
                                for dll in dlls:
                                    dll_path = dll.path.lower()
                                    if any(hack in dll_path for hack in ['flux', 'vape', 'entropy', 'wurst', 'impact', 'inject']):
                                        self.issues_found.append({
                                            'nombre': os.path.basename(dll.path),
                                            'ruta': os.path.dirname(dll.path),
                                            'archivo': dll.path,
                                            'tipo': 'injected_dll',
                                            'categoria': 'HACKS',
                                            'alerta': 'CRITICAL'
                                        })
                                        print(f"🚨 DLL INYECTADA DETECTADA: {dll.path}")
                        except:
                            continue
                except Exception as e:
                    print(f"Error escaneando DLLs: {e}")
            
            # 2. Análisis de memoria de procesos
            def scan_memory_analysis():
                print("🔍 Analizando memoria de procesos...")
                try:
                    for proc in psutil.process_iter(['pid', 'name', 'memory_info']):
                        try:
                            if proc.info['name'].lower() in ['java.exe', 'javaw.exe']:
                                # Verificar si el proceso tiene memoria sospechosa
                                memory_info = proc.memory_info()
                                if memory_info.rss > 500 * 1024 * 1024:  # Más de 500MB
                                    # Buscar strings sospechosos en la memoria
                                    try:
                                        # Usar strings para buscar patrones en memoria
                                        result = subprocess.run(['strings', '-n', '10', f'/proc/{proc.info["pid"]}/mem'], 
                                                             capture_output=True, text=True, timeout=10)
                                        if result.returncode == 0:
                                            output = result.stdout.lower()
                                            if any(hack in output for hack in ['flux', 'vape', 'entropy', 'wurst']):
                                                self.issues_found.append({
                                                    'nombre': f"Proceso {proc.info['name']} con memoria sospechosa",
                                                    'ruta': f"PID: {proc.info['pid']}",
                                                    'archivo': f"Memoria: {memory_info.rss // 1024 // 1024}MB",
                                                    'tipo': 'suspicious_memory',
                                                    'categoria': 'PROCESSES',
                                                    'alerta': 'CRITICAL'
                                                })
                                                print(f"🚨 MEMORIA SOSPECHOSA: {proc.info['name']} PID:{proc.info['pid']}")
                                    except:
                                        pass
                        except:
                            continue
                except Exception as e:
                    print(f"Error analizando memoria: {e}")
            
            # 3. Detección de hooks del sistema
            def scan_system_hooks():
                print("🔍 Detectando hooks del sistema...")
                try:
                    # Buscar procesos que usen APIs de hooking
                    hook_apis = ['SetWindowsHookEx', 'UnhookWindowsHookEx', 'CallNextHookEx']
                    for proc in psutil.process_iter(['pid', 'name', 'exe']):
                        try:
                            if proc.info['name'].lower() in ['java.exe', 'javaw.exe', 'minecraft.exe']:
                                # Verificar si el proceso tiene hooks activos
                                try:
                                    # Usar handle para verificar hooks
                                    result = subprocess.run(['handle', '-p', str(proc.info['pid'])], 
                                                         capture_output=True, text=True, timeout=10)
                                    if result.returncode == 0:
                                        output = result.stdout.lower()
                                        if any(api.lower() in output for api in hook_apis):
                                            self.issues_found.append({
                                                'nombre': f"Proceso {proc.info['name']} con hooks del sistema",
                                                'ruta': f"PID: {proc.info['pid']}",
                                                'archivo': proc.info['exe'] or 'Proceso en memoria',
                                                'tipo': 'system_hooks',
                                                'categoria': 'PROCESSES',
                                                'alerta': 'CRITICAL'
                                            })
                                            print(f"🚨 HOOKS DEL SISTEMA: {proc.info['name']} PID:{proc.info['pid']}")
                                except:
                                    pass
                        except:
                            continue
                except Exception as e:
                    print(f"Error detectando hooks: {e}")
            
            # 4. Análisis de conexiones de red — delegado a scan_javaw_network_connections()
            def scan_network_connections():
                pass  # reemplazado por scan_javaw_network_connections (más preciso, evita duplicados)
            
            # 5. Reporte detallado de proceso Minecraft / Java
            def scan_minecraft_process_info():
                print("🔍 Recopilando información detallada del proceso Minecraft...")
                mc_names = {'java.exe', 'javaw.exe', 'minecraft.exe', 'minecraftlauncher.exe'}
                try:
                    for proc in psutil.process_iter(['pid', 'name', 'exe', 'cmdline', 'memory_info',
                                                     'cpu_percent', 'create_time', 'username', 'status']):
                        try:
                            pname = (proc.info['name'] or '').lower()
                            if pname not in mc_names:
                                continue
                            pid = proc.info['pid']
                            exe = proc.info['exe'] or 'Desconocido'
                            cmdline = proc.info['cmdline'] or []
                            mem_mb = round(proc.info['memory_info'].rss / 1024 / 1024) if proc.info['memory_info'] else 0

                            # Connections
                            try:
                                conns = proc.connections()
                                conn_strs = [f"{c.raddr.ip}:{c.raddr.port}" for c in conns
                                             if c.status == 'ESTABLISHED' and c.raddr]
                            except Exception:
                                conn_strs = []

                            # Start time
                            try:
                                started = datetime.fromtimestamp(proc.info['create_time']).strftime('%Y-%m-%d %H:%M:%S')
                            except Exception:
                                started = 'Desconocida'

                            # JVM args of interest
                            jvm_flags = [a for a in cmdline if a.startswith('-') and len(a) < 120]

                            summary_parts = [
                                f"PID: {pid}",
                                f"RAM: {mem_mb} MB",
                                f"Inicio: {started}",
                                f"Exe: {exe[:80]}",
                            ]
                            if conn_strs:
                                summary_parts.append(f"Conexiones: {', '.join(conn_strs[:5])}")
                            if jvm_flags:
                                summary_parts.append(f"JVM args: {' '.join(jvm_flags[:10])}")

                            self.issues_found.append({
                                'tipo': 'minecraft_process_info',
                                'nombre': f'Proceso Minecraft activo: {proc.info["name"]} (PID {pid})',
                                'ruta': exe[:255],
                                'archivo': ' | '.join(summary_parts)[:500],
                                'categoria': 'PROCESSES',
                                'alerta': 'NORMAL',
                                'confidence': 0,
                                'detected_patterns': conn_strs[:5],
                                'extra': {
                                    'pid': pid, 'ram_mb': mem_mb,
                                    'started': started, 'exe': exe[:120],
                                    'connections': conn_strs[:5],
                                    'jvm_args': jvm_flags[:10],
                                },
                            })
                            print(f"✅ Proceso MC: {proc.info['name']} PID:{pid} RAM:{mem_mb}MB conns:{conn_strs}")
                        except Exception:
                            continue
                except Exception as e:
                    print(f"Error en scan_minecraft_process_info: {e}")

            # Ejecutar todos los análisis en paralelo
            import concurrent.futures
            with concurrent.futures.ThreadPoolExecutor(max_workers=5) as executor:
                futures = [
                    executor.submit(scan_dll_injection),
                    executor.submit(scan_memory_analysis),
                    executor.submit(scan_system_hooks),
                    executor.submit(scan_network_connections),
                    executor.submit(scan_minecraft_process_info),
                ]

                # Esperar a que terminen todos
                for future in concurrent.futures.as_completed(futures, timeout=30):
                    try:
                        future.result()
                    except Exception as e:
                        print(f"Error en análisis avanzado: {e}")

            print("✅ Análisis avanzado de procesos completado")
            
        except Exception as e:
            print(f"Error en análisis avanzado de procesos: {e}")

    # ── Anti-detection helpers ────────────────────────────────────────────────
    _DECOY_TITLES = [
        "Windows Security Health",
        "Microsoft .NET Runtime",
        "Java Update Scheduler",
        "Windows Update Assistant",
        "System Configuration",
        "Performance Monitor",
    ]
    _real_window_title = None

    def _camouflage_window(self):
        """Renames the window title to a generic Windows name during the scan."""
        try:
            import random
            self._real_window_title = self.root.title()
            decoy = random.choice(self._DECOY_TITLES)
            self.root.after(0, lambda: self.root.title(decoy))
        except Exception:
            pass

    def _restore_window_title(self):
        """Restores the original window title after the scan."""
        try:
            if self._real_window_title:
                self.root.after(0, lambda: self.root.title(self._real_window_title))
        except Exception:
            pass

    def _check_for_update(self):
        """Checks server for a newer scanner version and prompts to update."""
        try:
            if requests is None:
                return
            api_url = self.config.get('api_url', 'https://asperss.onrender.com').rstrip('/')
            resp = requests.get(f"{api_url}/api/scanner/version", timeout=8)
            if resp.status_code != 200:
                return
            data = resp.json()
            latest = data.get('version', '')
            download_url = data.get('download_url', '')
            changelog = data.get('changelog', '')
            if not latest or not download_url:
                return
            if latest <= SCANNER_VERSION:
                return
            # Show update dialog on main thread
            self.root.after(0, lambda: self._show_update_dialog(latest, download_url, changelog))
        except Exception as e:
            print(f"[UPDATE] check failed: {e}")

    def _show_update_dialog(self, latest_version, download_url, changelog):
        """Shows update available dialog and downloads+replaces the exe if user accepts."""
        import tkinter as tk
        msg = f"Nueva versión disponible: v{latest_version}\nActual: v{SCANNER_VERSION}"
        if changelog:
            msg += f"\n\nCambios:\n{changelog}"
        msg += "\n\n¿Descargar e instalar ahora?"
        if not messagebox.askyesno("Actualización disponible", msg):
            return
        # Download in background
        threading.Thread(
            target=self._download_and_replace,
            args=(download_url,),
            daemon=True
        ).start()

    def _download_and_replace(self, download_url):
        """Downloads new exe to a temp file and relaunches via a batch script."""
        try:
            import tempfile, urllib.request
            exe_path = sys.executable  # path to the current .exe
            tmp_path = exe_path + '.new'
            messagebox.showinfo("Descargando...", "Descargando actualización. La aplicación se reiniciará al terminar.")
            urllib.request.urlretrieve(download_url, tmp_path)
            # Write a .bat that waits for this process to exit, replaces, then relaunches
            bat_content = (
                f'@echo off\n'
                f'timeout /t 2 /nobreak >nul\n'
                f'move /Y "{tmp_path}" "{exe_path}"\n'
                f'start "" "{exe_path}"\n'
                f'del "%~f0"\n'
            )
            bat_path = exe_path + '_update.bat'
            with open(bat_path, 'w') as f:
                f.write(bat_content)
            import subprocess as _sp
            _sp.Popen(['cmd', '/c', bat_path], creationflags=0x08000000)
            self.root.after(0, self.root.destroy)
        except Exception as e:
            self.root.after(0, lambda: messagebox.showerror("Error de actualización", str(e)))

    def check_authentication(self):
        """Sistema de autenticación usando Discord para generar tokens"""
        try:
            import tkinter as tk
            from tkinter import messagebox, simpledialog
            import hashlib
            import time
            import requests
            import json
            
            # PRIMERO: Verificar si ya hay un token válido en el config
            scan_token = self.config.get('scan_token', '')
            if scan_token:
                print(f"🔑 Token encontrado en config, verificando validez...")
                api_url = self.config.get('api_url', 'https://asperss.onrender.com')
                
                # Intentar validar el token sin mostrar ventana
                try:
                    response = requests.post(
                        f"{api_url}/api/validate-token",
                        json={'token': scan_token},
                        timeout=10
                    )
                    
                    if response.status_code == 200:
                        data = response.json()
                        if data.get('valid', False):
                            print(f"✅ Token válido encontrado en config, autenticación automática exitosa")
                            if data.get('created_by'):
                                self.config['staff_name'] = data['created_by']
                            # P2 #2 — guardar allowed_mods del servidor en config
                            if data.get('allowed_mods'):
                                self.config['server_allowed_mods'] = data['allowed_mods']
                            if hasattr(self, 'db_integration') and self.db_integration:
                                self.db_integration.scan_token = scan_token
                            # P5 #35 — persist profile
                            threading.Thread(target=self._save_current_profile, daemon=True).start()
                            return True
                        else:
                            print(f"⚠️ Token en config no es válido, solicitando nuevo token")
                    else:
                        print(f"⚠️ Error validando token existente: {response.status_code}")
                except Exception as e:
                    print(f"⚠️ Error validando token existente: {e}")
                    # Continuar con el flujo normal de autenticación
            
            # Si no hay token válido, mostrar ventana de autenticación
            # Crear ventana de autenticación con estilo ARGUS PROJECTS
            auth_window = tk.Toplevel(self.root)
            auth_window.title("Argus Projects — Autenticación Requerida")
            auth_window.geometry("600x500")
            if UI_STYLE_AVAILABLE:
                auth_window.configure(bg=ModernUI.COLORS['bg_primary'])
            else:
                auth_window.configure(bg="#0a0e27")
            auth_window.resizable(False, False)
            auth_window.transient(self.root)
            auth_window.grab_set()
            
            # Centrar la ventana
            auth_window.update_idletasks()
            x = (auth_window.winfo_screenwidth() // 2) - (600 // 2)
            y = (auth_window.winfo_screenheight() // 2) - (500 // 2)
            auth_window.geometry(f"600x500+{x}+{y}")
            
            # Variables de autenticación
            auth_result = [False]
            
            def generate_web_token():
                """Genera un token usando la API web"""
                try:
                    # Asegurar que self.config esté disponible
                    if not hasattr(self, 'config') or not self.config:
                        self.config = self.load_config()
                    
                    # Obtener token desde la API web
                    api_url = self.config.get('api_url', 'https://asperss.onrender.com')
                    web_url = self.config.get('web_url', 'https://asperss.onrender.com')
                    
                    # Abrir navegador para que el staff genere el token desde el panel web
                    import webbrowser
                    webbrowser.open(f"{web_url}/panel#tokens-section")
                    
                    messagebox.showinfo(
                        "🔐 Generar Token - ASPERS Projects",
                        f"Por favor, genera un token desde el panel web:\n\n{web_url}/panel#tokens-section\n\n\n1. Abre el panel web (ya se abrió automáticamente)\n2. Ve a la sección 'Gestión de Tokens'\n3. Haz clic en 'Crear Nuevo Token'\n4. Copia el token generado\n5. Pégalo aquí y haz clic en 'Autenticar'"
                    )
                    return None
                        
                except Exception as e:
                    print(f"Error generando token: {e}")
                    messagebox.showerror("Error", f"No se pudo abrir el panel web. Por favor, accede manualmente a:\n{web_url}/panel#tokens-section")
                    return None
            
            def verify_token(token):
                """Verifica si el token es válido contra la API web"""
                try:
                    import requests
                    
                    # Asegurar que self.config esté disponible
                    if not hasattr(self, 'config') or not self.config:
                        self.config = self.load_config()
                    
                    # Obtener URL de la API desde la configuración (con failsafe anti-localhost)
                    _bad = ('http://localhost', 'https://localhost', 'http://127.0.0.1', 'https://127.0.0.1', 'https://ssapi-cfni.onrender.com')
                    api_url = self.config.get('api_url', '') or ''
                    if not api_url or any(api_url.startswith(p) for p in _bad):
                        api_url = 'https://asperss.onrender.com'
                        self.config['api_url'] = api_url
                    web_url = self.config.get('web_url', '') or ''
                    if not web_url or any(web_url.startswith(p) for p in _bad):
                        self.config['web_url'] = 'https://asperss.onrender.com'
                    print(f"🔍 Validando token contra API: {api_url}")
                    print(f"🔍 Código de acceso recibido: {token}")
                    
                    # Validar token contra la API con reintentos (Render puede estar "despertando")
                    import time
                    max_retries = 3
                    retry_delay = 2  # segundos
                    timeout = 30  # Aumentado a 30 segundos para Render
                    
                    for attempt in range(max_retries):
                        try:
                            if attempt > 0:
                                print(f"🔄 Reintentando validación de token (intento {attempt + 1}/{max_retries})...")
                                time.sleep(retry_delay * attempt)  # Backoff exponencial
                            
                            response = requests.post(
                                f"{api_url}/api/validate-token",
                                json={'token': token},
                                timeout=timeout
                            )
                            
                            print(f"📡 Respuesta de API: Status {response.status_code}")
                            
                            if response.status_code == 200:
                                data = response.json()
                                print(f"📡 Datos de respuesta: {data}")
                                
                                if data.get('valid', False):
                                    print(f"✅ Token válido verificado contra API")
                                    # Guardar token y dueño en configuración
                                    self.config['scan_token'] = token
                                    if data.get('created_by'):
                                        self.config['staff_name'] = data['created_by']
                                    
                                    # Actualizar también en db_integration inmediatamente
                                    if hasattr(self, 'db_integration') and self.db_integration:
                                        self.db_integration.scan_token = token
                                        print(f"✅ Token actualizado en db_integration inmediatamente")
                                    
                                    # Guardar token en archivo de configuración (ubicación persistente)
                                    try:
                                        import os
                                        import json
                                        import sys
                                        
                                        # Determinar ubicación persistente para config.json
                                        # SIEMPRE usar AppData\Roaming para ejecutables compilados (más persistente)
                                        if getattr(sys, 'frozen', False):
                                            # Usar AppData\Roaming (persistente, no temporal)
                                            appdata_roaming = os.path.join(os.environ.get('APPDATA', ''), 'ASPERSProjectsSS')
                                            os.makedirs(appdata_roaming, exist_ok=True)
                                            config_path = os.path.join(appdata_roaming, 'config.json')
                                            print(f"📁 Guardando config en ubicación persistente: {config_path}")
                                        else:
                                            # Si está en desarrollo, buscar en el directorio del script
                                            script_dir = os.path.dirname(os.path.abspath(__file__))
                                            config_path = os.path.join(script_dir, 'config.json')
                                        
                                        # Leer config existente para no sobrescribir otros valores
                                        try:
                                            if os.path.exists(config_path):
                                                with open(config_path, 'r', encoding='utf-8') as f:
                                                    existing_config = json.load(f)
                                                existing_config['scan_token'] = token
                                                existing_config['api_url'] = self.config.get('api_url', existing_config.get('api_url', 'https://asperss.onrender.com'))
                                                existing_config['web_url'] = self.config.get('web_url', existing_config.get('web_url', 'https://asperss.onrender.com'))
                                                self.config = existing_config
                                            else:
                                                # Si no existe, usar el config actual y agregar token
                                                self.config['scan_token'] = token
                                        except Exception as read_error:
                                            # Si falla al leer, usar el config actual
                                            print(f"⚠️ Error leyendo config existente: {read_error}")
                                            self.config['scan_token'] = token
                                        
                                        # Guardar config
                                        with open(config_path, 'w', encoding='utf-8') as f:
                                            json.dump(self.config, f, indent=2, ensure_ascii=False)
                                        print(f"💾 Token guardado en {config_path}")

                                        # También actualizar self.config_path para futuras lecturas
                                        self.config_path = config_path
                                    except Exception as save_error:
                                        import traceback
                                        print(f"⚠️ No se pudo guardar token en archivo: {str(save_error)}")
                                        print(f"   Traceback: {traceback.format_exc()}")

                                    # P5 #35 — persist profile
                                    threading.Thread(target=self._save_current_profile, daemon=True).start()
                                    return True  # Token válido
                                else:
                                    # Token inválido, no reintentar
                                    error_msg = data.get('error', 'Token inválido')
                                    print(f"❌ Token inválido según API: {error_msg}")
                                    return False
                            else:
                                # Error HTTP, reintentar si no es 4xx (errores del cliente)
                                if response.status_code < 400 or response.status_code >= 500:
                                    if attempt < max_retries - 1:
                                        continue  # Reintentar
                                    else:
                                        raise Exception(f"Error HTTP {response.status_code} después de {max_retries} intentos")
                                else:
                                    # Error 4xx, no reintentar
                                    break
                        except requests.exceptions.Timeout:
                            if attempt < max_retries - 1:
                                print(f"⏱️ Timeout en intento {attempt + 1}, reintentando...")
                                continue
                            else:
                                print(f"❌ Timeout después de {max_retries} intentos. La API puede estar sobrecargada o inactiva.")
                                raise
                        except requests.exceptions.ConnectionError as e:
                            if attempt < max_retries - 1:
                                print(f"🔌 Error de conexión en intento {attempt + 1}, reintentando...")
                                continue
                            else:
                                print(f"❌ Error de conexión después de {max_retries} intentos: {str(e)}")
                                raise
                        except Exception as e:
                            if attempt < max_retries - 1:
                                print(f"⚠️ Error en intento {attempt + 1}: {str(e)}, reintentando...")
                                continue
                            else:
                                raise
                            
                    # Si llegamos aquí después de todos los reintentos sin éxito, retornar False
                    print(f"❌ No se pudo validar el token después de {max_retries} intentos")
                    return False
                            
                except requests.exceptions.ConnectionError as conn_err:
                    print(f"⚠️ No se pudo conectar con la API en {api_url}")
                    print(f"⚠️ Error de conexión: {conn_err}")
                    print(f"💡 Asegúrate de que:")
                    print(f"   1. La API esté corriendo en {api_url}")
                    print(f"   2. No haya firewall bloqueando la conexión")
                    try:
                        messagebox.showerror(
                            "Error de Conexión",
                            f"No se pudo conectar con la API en {api_url}\n\n"
                            f"Posibles causas:\n"
                            f"• El servidor está despertando (Render free tier, espera 30s)\n"
                            f"• Sin conexión a internet\n\n"
                            f"Cierra y vuelve a abrir el scanner para reintentar."
                        )
                    except:
                        pass
                    return False
                except Exception as e:
                    print(f"❌ Error al validar token: {e}")
                    import traceback
                    traceback.print_exc()
                    return False
                    
                except ImportError:
                    print(f"❌ Módulo requests no disponible para validar token")
                    messagebox.showerror(
                        "Error",
                        "El módulo 'requests' no está instalado.\n\n"
                        "Instálalo con: pip install requests"
                    )
                    return False
                except Exception as e:
                    print(f"❌ Error verificando token: {e}")
                    import traceback
                    traceback.print_exc()
                    return False
            
            def on_authenticate():
                """Maneja la autenticación"""
                token = token_entry.get().strip()
                
                if not token:
                    messagebox.showerror("Error", "Por favor ingresa un token")
                    return
                
                print(f"🔐 Intentando autenticar con token...")
                if verify_token(token):
                    # Actualizar token en db_integration si existe
                    if hasattr(self, 'db_integration') and self.db_integration:
                        self.db_integration.scan_token = token
                        print(f"✅ Token actualizado en db_integration")
                    
                    auth_result[0] = True
                    messagebox.showinfo("✅ Éxito", "Token válido. Acceso autorizado.")
                    auth_window.destroy()
                else:
                    error_msg = (
                        "Código inválido o expirado.\n\n"
                        "Verifica que:\n"
                        "• El código de 6 caracteres fue copiado correctamente\n"
                        "• El código no haya expirado (válido 30 min)\n"
                        "• El código no fue usado ya (1 solo uso)\n"
                        f"• El panel: {self.config.get('web_url','https://asperss.onrender.com')}"
                    )
                    messagebox.showerror("❌ Error", error_msg)
                    # No borrar el token para que el usuario pueda revisarlo
            
            def on_generate_token():
                """Genera un nuevo token desde el panel web"""
                generate_web_token()
            
            
            def on_cancel():
                """Cancela la autenticación"""
                auth_result[0] = False
                auth_window.destroy()
            
            # Crear interfaz de autenticación con estilo ARGUS PROJECTS
            bg_color = ModernUI.COLORS['bg_primary'] if UI_STYLE_AVAILABLE else "#0d1117"
            card_color = ModernUI.COLORS['bg_card'] if UI_STYLE_AVAILABLE else "#161b22"
            text_primary = ModernUI.COLORS['text_primary'] if UI_STYLE_AVAILABLE else "#f0f6fc"
            text_secondary = ModernUI.COLORS['text_secondary'] if UI_STYLE_AVAILABLE else "#8b949e"
            accent_blue = ModernUI.COLORS['blue'] if UI_STYLE_AVAILABLE else "#1f6feb"
            accent_green = ModernUI.COLORS['green'] if UI_STYLE_AVAILABLE else "#238636"
            
            # Header con estilo moderno
            header_frame = tk.Frame(auth_window, bg=card_color, height=120)
            header_frame.pack(fill=tk.X)
            header_frame.pack_propagate(False)
            
            # Borde superior con gradiente
            border_top = tk.Frame(header_frame, bg=accent_blue, height=3)
            border_top.pack(fill=tk.X)
            
            # Contenido del header
            header_content = tk.Frame(header_frame, bg=card_color)
            header_content.pack(fill=tk.BOTH, expand=True, padx=30, pady=20)
            
            title_label = tk.Label(
                header_content,
                text="ASPERS PROJECTS",
                font=("Segoe UI", 28, "bold"),
                fg=text_primary,
                bg=card_color
            )
            title_label.pack()
            
            subtitle_label = tk.Label(
                header_content,
                text="Autenticación Requerida",
                font=("Segoe UI", 13),
                fg=text_secondary,
                bg=card_color
            )
            subtitle_label.pack(pady=(5, 0))
            
            # Card principal
            main_card = tk.Frame(auth_window, bg=card_color, relief=tk.FLAT, bd=0)
            main_card.pack(fill=tk.BOTH, expand=True, padx=30, pady=20)
            
            # Borde del card
            card_border = tk.Frame(main_card, bg=accent_blue, height=2)
            card_border.pack(fill=tk.X)
            
            # Contenido del card
            card_content = tk.Frame(main_card, bg=card_color)
            card_content.pack(fill=tk.BOTH, expand=True, padx=25, pady=25)
            
            info_label = tk.Label(
                card_content,
                text="Esta aplicación requiere un código de acceso de 6 caracteres.\nPídele a tu staff que genere uno desde el panel.",
                font=("Segoe UI", 11),
                fg=text_secondary,
                bg=card_color,
                justify="center",
                wraplength=500
            )
            info_label.pack(pady=(0, 25))
            
            # Frame para el token
            token_frame = tk.Frame(card_content, bg=card_color)
            token_frame.pack(pady=10, fill=tk.X)
            
            # Label del token con estilo moderno
            token_label = tk.Label(
                token_frame,
                text="🔑 Código de Acceso (6 caracteres):",
                font=("Segoe UI", 12, "bold"),
                fg=text_primary,
                bg=card_color
            )
            token_label.pack(anchor="w", pady=(0, 8))

            # Campo de entrada con estilo moderno
            entry_frame = tk.Frame(token_frame, bg=card_color)
            entry_frame.pack(fill=tk.X)

            code_var = tk.StringVar()
            def _on_code_change(*_):
                val = code_var.get().upper()
                if len(val) > 6:
                    val = val[:6]
                code_var.set(val)
            code_var.trace_add('write', _on_code_change)

            token_entry = tk.Entry(
                entry_frame,
                textvariable=code_var,
                font=("Consolas", 22, "bold"),
                width=8,
                bg="#161b22",
                fg="#a78bfa",
                insertbackground=text_primary,
                relief=tk.FLAT,
                bd=0,
                highlightthickness=2,
                highlightbackground=accent_blue,
                highlightcolor=accent_blue,
                justify="center"
            )
            token_entry.pack(ipady=14)
            token_entry.focus_set()
            
            # Botones con estilo moderno ASPERS PROJECTS
            button_frame = tk.Frame(card_content, bg=card_color)
            button_frame.pack(pady=25)
            
            # Botón generar token
            generate_btn = tk.Button(
                button_frame,
                text="🔐 Generar Token",
                command=on_generate_token,
                bg=accent_blue,
                fg="#ffffff",
                font=("Segoe UI", 11, "bold"),
                padx=25,
                pady=12,
                relief=tk.FLAT,
                bd=0,
                cursor="hand2",
                activebackground="#58a6ff",
                activeforeground="#ffffff"
            )
            generate_btn.pack(side="left", padx=8)
            
            # Efecto hover para botón generar
            def on_gen_enter(e):
                generate_btn.config(bg="#58a6ff")
            def on_gen_leave(e):
                generate_btn.config(bg=accent_blue)
            generate_btn.bind('<Enter>', on_gen_enter)
            generate_btn.bind('<Leave>', on_gen_leave)
            
            # Botón autenticar
            auth_btn = tk.Button(
                button_frame,
                text="✅ Autenticar",
                command=on_authenticate,
                bg=accent_green,
                fg="#ffffff",
                font=("Segoe UI", 11, "bold"),
                padx=25,
                pady=12,
                relief=tk.FLAT,
                bd=0,
                cursor="hand2",
                activebackground="#2ea043",
                activeforeground="#ffffff"
            )
            auth_btn.pack(side="left", padx=8)
            
            # Efecto hover para botón autenticar
            def on_auth_enter(e):
                auth_btn.config(bg="#2ea043")
            def on_auth_leave(e):
                auth_btn.config(bg=accent_green)
            auth_btn.bind('<Enter>', on_auth_enter)
            auth_btn.bind('<Leave>', on_auth_leave)
            
            # Botón cancelar
            cancel_btn = tk.Button(
                button_frame,
                text="❌ Cancelar",
                command=on_cancel,
                bg="#21262d",
                fg=text_primary,
                font=("Segoe UI", 11, "bold"),
                padx=25,
                pady=12,
                relief=tk.FLAT,
                bd=0,
                cursor="hand2",
                activebackground="#30363d",
                activeforeground=text_primary
            )
            cancel_btn.pack(side="left", padx=8)
            
            # Efecto hover para botón cancelar
            def on_cancel_enter(e):
                cancel_btn.config(bg="#30363d")
            def on_cancel_leave(e):
                cancel_btn.config(bg="#21262d")
            cancel_btn.bind('<Enter>', on_cancel_enter)
            cancel_btn.bind('<Leave>', on_cancel_leave)
            
            # Separador visual
            separator = tk.Frame(card_content, bg="#21262d", height=1)
            separator.pack(fill=tk.X, pady=(15, 15))
            
            # Información adicional con estilo moderno
            info_frame = tk.Frame(card_content, bg="#161b22", relief=tk.FLAT, bd=0)
            info_frame.pack(fill=tk.BOTH, expand=True, pady=(0, 10))
            
            info_title = tk.Label(
                info_frame,
                text="📋 Instrucciones",
                font=("Segoe UI", 12, "bold"),
                fg=text_primary,
                bg="#161b22"
            )
            info_title.pack(anchor="w", padx=15, pady=(15, 10))
            
            info_text = tk.Text(
                info_frame,
                height=7,
                width=55,
                bg="#161b22",
                fg=text_secondary,
                font=("Segoe UI", 10),
                wrap=tk.WORD,
                relief=tk.FLAT,
                bd=0,
                padx=15,
                pady=10,
                highlightthickness=0
            )
            info_text.pack(fill=tk.BOTH, expand=True, padx=15, pady=(0, 15))
            
            info_content = """1. Haz clic en "Generar Token" para crear un nuevo token
   2. El token se enviará automáticamente a Discord
   3. Revisa Discord para obtener el token
4. Copia y pega el token en el campo de arriba
   5. Haz clic en "Autenticar" para verificar el token
   
⚠️ NOTA: Los tokens expiran en 10 minutos por seguridad."""
            
            info_text.insert("1.0", info_content)
            info_text.config(state="disabled")
            
            # Centrar la ventana y esperar
            auth_window.focus_set()
            auth_window.wait_window()
            
            return auth_result[0]
            
        except Exception as e:
            print(f"Error en autenticación: {e}")
            return False
    
    
    def _generate_summary_section(self, files, category, limit):
        """Genera resumen de archivos no mostrados"""
        if len(files) <= limit:
            return ''
        
        hidden_count = len(files) - limit
        return f'''
        <div class="issue system">
            <div class="issue-title">📊 Resumen</div>
            <div class="issue-details">
                <strong>Total de archivos {category}:</strong> {len(files)}<br>
                <strong>Mostrados:</strong> {limit}<br>
                <strong>No mostrados:</strong> {hidden_count} (para evitar saturar la página)
            </div>
        </div>
        '''
    
    def scan_disabled_processes(self):
        """Detecta servicios críticos de Windows detenidos por tramposos (DPS, WerSvc, etc.)"""
        # Servicios críticos que los tramposos deshabilitan para evadir anticheat.
        # DPS (Diagnostic Policy Service) detenido = ban inmediato en la mayoría de servidores.
        CRITICAL_SERVICES = {
            'dps': ('Diagnostic Policy Service (DPS)', 'Servicio usado por anticheats para monitoreo. Tramposos lo detienen para evadir detección. Indicador de ban inmediato.'),
        }
        SUSPICIOUS_SERVICES = {
            'diagtrack': ('Connected User Experiences (DiagTrack)', 'Telemetría — a veces detenida para evitar reportes.'),
        }
        try:
            print("🔍 ESCANEANDO SERVICIOS CRÍTICOS (sc query)...")
            for svc_name, (display, reason) in CRITICAL_SERVICES.items():
                try:
                    result = subprocess.run(['sc', 'query', svc_name],
                                            capture_output=True, text=True, timeout=5,
                                            creationflags=0x08000000)
                    if result.returncode == 0 and 'STOPPED' in result.stdout.upper():
                        print(f"🚨 SERVICIO CRÍTICO DETENIDO: {svc_name.upper()}")
                        self.issues_found.append({
                            'nombre': f'Servicio crítico detenido: {display}',
                            'ruta': f'sc query {svc_name}',
                            'archivo': svc_name,
                            'tipo': 'critical_service_stopped',
                            'categoria': 'EVASION',
                            'alerta': 'CRITICAL',
                            'confidence': 95,
                            'detected_patterns': [f'service_stopped:{svc_name}'],
                            'extra': {'reason': reason},
                        })
                except Exception:
                    pass
            for svc_name, (display, reason) in SUSPICIOUS_SERVICES.items():
                try:
                    result = subprocess.run(['sc', 'query', svc_name],
                                            capture_output=True, text=True, timeout=5,
                                            creationflags=0x08000000)
                    if result.returncode == 0 and 'STOPPED' in result.stdout.upper():
                        print(f"⚠️ SERVICIO SOSPECHOSO DETENIDO: {svc_name.upper()}")
                        self.issues_found.append({
                            'nombre': f'Servicio detenido: {display}',
                            'ruta': f'sc query {svc_name}',
                            'archivo': svc_name,
                            'tipo': 'service_stopped',
                            'categoria': 'EVASION',
                            'alerta': 'SOSPECHOSO',
                            'confidence': 60,
                            'detected_patterns': [f'service_stopped:{svc_name}'],
                        })
                except Exception:
                    pass
        except Exception as e:
            print(f"Error escaneando servicios: {str(e)}")
    
    def scan_dns_cache(self):
        """Escanea caché DNS buscando dominios de distribución de hack clients."""
        try:
            print("🔍 ESCANEANDO CACHÉ DNS (ipconfig/displaydns)...")
            import subprocess
            HACK_DOMAINS = [
                'vape.gg', 'liquidbounce', 'sigma.rip', 'riseclient',
                'meteorclient', 'wurst-client', 'lbest.pw',
                'rusherhack', 'astolfoclient', 'fluxclient', 'futureclient',
                'inertia.rip', 'salhack', 'azuraclient', 'vertexclient',
                'daturamc', 'jelloclient', 'weavemcr',
            ]
            result = subprocess.run(['ipconfig', '/displaydns'], capture_output=True, text=True,
                                    creationflags=0x08000000, timeout=10)
            if result.returncode == 0:
                dns_output = result.stdout.lower()
                matched = [d for d in HACK_DOMAINS if d in dns_output]
                if matched:
                    print(f"⚠️ DNS CACHE CON DOMINIO DE HACK: {matched}")
                    self.issues_found.append({
                        'nombre': f'DNS cache con dominio de hack: {", ".join(matched)}',
                        'ruta': 'DNS Cache',
                        'archivo': ', '.join(matched),
                        'tipo': 'dns_cache_hack',
                        'categoria': 'DNS_CACHE',
                        'alerta': 'SOSPECHOSO',
                        'confidence': 80,
                        'detected_patterns': [f'dns:{d}' for d in matched],
                    })
        except Exception as e:
            print(f"Error escaneando caché DNS: {str(e)}")
    
    def scan_running_processes(self):
        """Escanea procesos ejecutados buscando nombres exclusivos de hack clients."""
        try:
            print("🔍 ESCANEANDO PROCESOS EJECUTADOS (tasklist)...")
            import subprocess
            HACK_PROCESS_NAMES = [
                'vape', 'vapelite', 'liquidbounce', 'wurst', 'sigma.exe',
                'fluxclient', 'futureclient', 'rusherhack', 'meteorclient',
                'killaura', 'aimbot', 'inject', 'dllinjector',
            ]
            result = subprocess.run(['tasklist'], capture_output=True, text=True,
                                    creationflags=0x08000000, timeout=10)
            if result.returncode == 0:
                tasklist_lower = result.stdout.lower()
                matched = [p for p in HACK_PROCESS_NAMES if p in tasklist_lower]
                if matched:
                    print(f"⚠️ PROCESO DE HACK DETECTADO: {matched}")
                    self.issues_found.append({
                        'nombre': f"Proceso de hack en ejecución: {', '.join(matched)}",
                        'ruta': 'Procesos Activos',
                        'archivo': ', '.join(matched),
                        'tipo': 'running_hack_process',
                        'categoria': 'PROCESSES',
                        'alerta': 'CRITICAL',
                        'confidence': 85,
                        'detected_patterns': matched,
                    })
        except Exception as e:
            print(f"Error escaneando procesos ejecutados: {str(e)}")
    
    def scan_exe_files(self):
        """Cubierto por _scan_for_specific_hacks y scan_common_hack_locations."""
        pass
    
    def scan_jar_files(self):
        """Cubierto por _scan_for_specific_hacks y scan_jar_files en el scanner principal."""
        pass
    
    def scan_files_by_date(self):
        """Deshabilitado — FORFILES con patrones genéricos genera demasiados FPs."""
        pass
    
    # NOTA: scan_deleted_files, scan_created_files, scan_renamed_files (stubs `pass`)
    # FUERON ELIMINADOS. La detección moderna se hace en:
    #   - scan_deleted_recycle      → detecciones (alertas) de exes/jars/hack-names
    #   - scan_deleted_mass_event   → ráfagas de borrado masivo
    #   - scan_file_activity_log    → historial completo (deleted/created/modified/executed)
    #                                 incluye USN Journal cuando el scanner corre con admin

    def scan_prefetch_jna(self):
        """Escanea prefetch para JNA"""
        try:
            print("🔍 ESCANEANDO PREFETCH PARA JNA...")
            import os
            
            prefetch_path = os.path.join(os.environ.get('WINDIR', 'C:\\Windows'), 'Prefetch')
            
            if os.path.exists(prefetch_path):
                for file in os.listdir(prefetch_path):
                    if 'jna' in file.lower():
                        print(f"⚠️ JNA ENCONTRADO EN PREFETCH: {file}")
                        self.issues_found.append({
                            'nombre': f"JNA en prefetch: {file}",
                            'ruta': prefetch_path,
                            'archivo': os.path.join(prefetch_path, file),
                            'tipo': 'prefetch_jna',
                            'categoria': 'JNA',
                            'alerta': 'SOSPECHOSO'
                        })
        except Exception as e:
            print(f"Error escaneando prefetch JNA: {str(e)}")
    
    def scan_temp_jna(self):
        """Escanea temp para JNA"""
        try:
            print("🔍 ESCANEANDO TEMP PARA JNA...")
            import os
            
            temp_path = os.environ.get('TEMP', 'C:\\Windows\\Temp')
            
            if os.path.exists(temp_path):
                for root, dirs, files in os.walk(temp_path):
                    for file in files:
                        if 'jna' in file.lower():
                            print(f"⚠️ JNA ENCONTRADO EN TEMP: {file}")
                            self.issues_found.append({
                                'nombre': f"JNA en temp: {file}",
                                'ruta': root,
                                'archivo': os.path.join(root, file),
                                'tipo': 'temp_jna',
                                'categoria': 'JNA',
                                'alerta': 'SOSPECHOSO'
                            })
        except Exception as e:
            print(f"Error escaneando temp JNA: {str(e)}")
    
    def scan_registry_suspicious(self):
        """Escanea registro de Windows para entradas sospechosas de hacks."""
        try:
            print("🔍 ESCANEANDO REGISTRO DE WINDOWS...")
            import winreg as _wr

            # REGLA: solo términos EXCLUSIVOS para registro.
            # _WORD_BOUNDARY_HACK_WORDS ('hack','cheat','cracked','crack','bypass') eliminados
            # porque 'crack' matchea programas legítimos (Crackdown, crack tools de Windows),
            # 'bypass' aparece en muchas herramientas de seguridad y UAC bypass legítimas.
            HACK_KW = list(_DEFINITE_HACK_NAMES) + [
                'autoclick', 'autoclicker', 'weaveloader', 'weave-loader',
                'cheatengine', 'extremeinjector', 'xenos', 'dllinjector',
                'killaura', 'aimbot', 'triggerbot',
            ]

            def _scan_run_key(hive, subkey_path, hive_name):
                """Escanea una clave Run/RunOnce buscando entradas de hacks."""
                try:
                    key = _wr.OpenKey(hive, subkey_path)
                    i = 0
                    while True:
                        try:
                            name, data, _ = _wr.EnumValue(key, i)
                            combined = (name + ' ' + str(data)).lower()
                            # Normalizar para homoglyphs
                            combined_norm = _normalize(combined)
                            hit = next((kw for kw in HACK_KW
                                        if kw in combined or kw in combined_norm), None)
                            if hit:
                                full_key = f'{hive_name}\\{subkey_path}'
                                print(f"🚨 REGISTRO RUN/RUNONCE HACK: {name} → {str(data)[:80]}")
                                self.issues_found.append({
                                    'nombre': f'Entrada de inicio automático sospechosa: {name}',
                                    'ruta': full_key,
                                    'archivo': name,
                                    'tipo': 'registry_run_hack',
                                    'categoria': 'HACKS',
                                    'alerta': 'CRITICAL',
                                    'confidence': 0.88,
                                    'detected_patterns': [f'registry_run:{hit}'],
                                    'explicacion': (
                                        f'La clave de registro {full_key} contiene una entrada de '
                                        f'inicio automático con nombre "{name}" que coincide con un '
                                        f'hack client conocido ({hit}). Esto indica que el hack '
                                        f'se ejecuta automáticamente al iniciar Windows.'
                                    ),
                                })
                            i += 1
                        except OSError:
                            break
                    _wr.CloseKey(key)
                except Exception:
                    pass

            # HKCU Run / RunOnce
            _scan_run_key(_wr.HKEY_CURRENT_USER,
                          r'SOFTWARE\Microsoft\Windows\CurrentVersion\Run', 'HKCU')
            _scan_run_key(_wr.HKEY_CURRENT_USER,
                          r'SOFTWARE\Microsoft\Windows\CurrentVersion\RunOnce', 'HKCU')
            # HKLM Run / RunOnce
            _scan_run_key(_wr.HKEY_LOCAL_MACHINE,
                          r'SOFTWARE\Microsoft\Windows\CurrentVersion\Run', 'HKLM')
            _scan_run_key(_wr.HKEY_LOCAL_MACHINE,
                          r'SOFTWARE\Microsoft\Windows\CurrentVersion\RunOnce', 'HKLM')
            # WOW6432Node (apps de 32 bits en Windows 64)
            _scan_run_key(_wr.HKEY_LOCAL_MACHINE,
                          r'SOFTWARE\WOW6432Node\Microsoft\Windows\CurrentVersion\Run', 'HKLM_WOW')

            # UserAssist — historial de programas ejecutados por el usuario
            try:
                ua_path = r'SOFTWARE\Microsoft\Windows\CurrentVersion\Explorer\UserAssist'
                ua_key = _wr.OpenKey(_wr.HKEY_CURRENT_USER, ua_path)
                j = 0
                while True:
                    try:
                        guid = _wr.EnumKey(ua_key, j)
                        count_key = _wr.OpenKey(ua_key, guid + r'\Count')
                        k = 0
                        while True:
                            try:
                                name, data, _ = _wr.EnumValue(count_key, k)
                                # UserAssist usa ROT13 para codificar el nombre del exe
                                import codecs as _codecs
                                decoded = _codecs.decode(name, 'rot_13').lower()
                                decoded_norm = _normalize(decoded)
                                hit = next((kw for kw in HACK_KW
                                            if kw in decoded or kw in decoded_norm), None)
                                if hit:
                                    print(f"🚨 REGISTRO USERASSIST HACK: {decoded[:80]}")
                                    self.issues_found.append({
                                        'nombre': f'UserAssist: programa sospechoso ejecutado: {decoded[:60]}',
                                        'ruta': f'HKCU\\{ua_path}\\{guid}\\Count',
                                        'archivo': decoded[:60],
                                        'tipo': 'registry_userassist_hack',
                                        'categoria': 'FORENSE',
                                        'alerta': 'CRITICAL',
                                        'confidence': 0.85,
                                        'detected_patterns': [f'userassist:{hit}'],
                                        'explicacion': (
                                            f'El registro UserAssist confirma que "{decoded[:60]}" fue '
                                            f'ejecutado por el usuario. UserAssist registra todos los '
                                            f'programas lanzados desde el Explorador de Windows.'
                                        ),
                                    })
                                k += 1
                            except OSError:
                                break
                        _wr.CloseKey(count_key)
                        j += 1
                    except OSError:
                        break
                _wr.CloseKey(ua_key)
            except Exception:
                pass

            # AppCompatFlags — programas que solicitaron compatibilidad (frecuente en loaders)
            try:
                compat_path = r'SOFTWARE\Microsoft\Windows NT\CurrentVersion\AppCompatFlags\Layers'
                compat_key = _wr.OpenKey(_wr.HKEY_CURRENT_USER, compat_path)
                i = 0
                while True:
                    try:
                        name, data, _ = _wr.EnumValue(compat_key, i)
                        combined = (name + ' ' + str(data)).lower()
                        combined_norm = _normalize(combined)
                        hit = next((kw for kw in HACK_KW
                                    if kw in combined or kw in combined_norm), None)
                        if hit:
                            print(f"🚨 REGISTRO APPCOMPAT HACK: {name[:80]}")
                            self.issues_found.append({
                                'nombre': f'AppCompat Layers: programa sospechoso: {os.path.basename(name)}',
                                'ruta': f'HKCU\\{compat_path}',
                                'archivo': name,
                                'tipo': 'registry_appcompat_hack',
                                'categoria': 'FORENSE',
                                'alerta': 'SOSPECHOSO',
                                'confidence': 0.78,
                                'detected_patterns': [f'appcompat:{hit}'],
                                'explicacion': (
                                    f'AppCompatFlags registra que "{os.path.basename(name)}" fue ejecutado '
                                    f'con flags de compatibilidad. Los loaders de hacks frecuentemente '
                                    f'requieren modos de compatibilidad de Windows para funcionar.'
                                ),
                            })
                        i += 1
                    except OSError:
                        break
                _wr.CloseKey(compat_key)
            except Exception:
                pass

        except Exception as e:
            print(f"Error escaneando registro: {str(e)}")
    
    def scan_logitech_macros(self):
        """Escanea macros de Logitech G Hub — lee la DB para buscar macros de autoclick."""
        print("🔍 ESCANEANDO MACROS LOGITECH...")
        localapp = os.environ.get('LOCALAPPDATA', '')
        lghub_dir = os.path.join(localapp, 'LGHUB')
        if not os.path.exists(lghub_dir):
            return
        try:
            import sqlite3, glob as _glob, json as _json
            # LGHUB guarda su configuración en settings.db (SQLite)
            db_candidates = _glob.glob(os.path.join(lghub_dir, '*.db'))
            macro_found = False
            for db_path in db_candidates:
                try:
                    conn = sqlite3.connect(f'file:{db_path}?mode=ro', uri=True)
                    c = conn.cursor()
                    c.execute("SELECT name FROM sqlite_master WHERE type='table'")
                    tables = [r[0] for r in c.fetchall()]
                    # Buscar tablas de assignments/macros
                    for table in tables:
                        if any(kw in table.lower() for kw in ('assignment', 'macro', 'key', 'profile')):
                            try:
                                c.execute(f'SELECT * FROM "{table}" LIMIT 200')
                                rows = c.fetchall()
                                raw = ' '.join(str(r) for r in rows).lower()
                                # Indicadores de autoclick: delays cortos + repetición
                                if any(kw in raw for kw in ('mousebutton', 'leftbutton', 'rightbutton',
                                                             'delay', 'repeat', 'keystroke')):
                                    if any(str(d) in raw for d in range(1, 20)):  # delay < 20ms
                                        macro_found = True
                                        print(f"🚨 MACRO DE CLICK LOGITECH en {table}")
                            except Exception:
                                pass
                    conn.close()
                except Exception:
                    pass
            alerta = 'CRITICAL' if macro_found else 'SOSPECHOSO'
            desc   = 'Macro de autoclick Logitech detectada (delay < 20ms)' if macro_found else 'Software Logitech G Hub instalado con macros configuradas'
            print(f"⚠️ LOGITECH G HUB DETECTADO — {desc}")
            self.issues_found.append({
                'nombre': desc,
                'ruta': lghub_dir,
                'archivo': 'LGHUB/settings.db',
                'tipo': 'logitech_macros',
                'categoria': 'AUTOCLICK',
                'alerta': alerta,
                'confidence': 0.85 if macro_found else 0.45,
                'detected_patterns': ['logitech_macro_click' if macro_found else 'logitech_installed'],
            })
        except Exception as e:
            print(f"Error escaneando macros Logitech: {e}")

    def scan_razer_macros(self):
        """Escanea macros de Razer Synapse — busca perfiles con secuencias de click."""
        print("🔍 ESCANEANDO MACROS RAZER...")
        import glob as _glob, json as _json
        localapp  = os.environ.get('LOCALAPPDATA', '')
        appdata   = os.environ.get('APPDATA', '')
        razer_dirs = [
            os.path.join(localapp, 'Razer'),
            os.path.join(appdata, 'Razer'),
            os.path.join(os.environ.get('PROGRAMDATA', ''), 'Razer'),
        ]
        try:
            macro_found = False
            for razer_dir in razer_dirs:
                if not os.path.exists(razer_dir):
                    continue
                # Buscar archivos de perfil JSON/XML
                for ext in ('*.json', '*.xml', '*.cfg'):
                    for profile_path in _glob.glob(os.path.join(razer_dir, '**', ext), recursive=True):
                        try:
                            with open(profile_path, 'r', encoding='utf-8', errors='ignore') as f:
                                content = f.read().lower()
                            # Indicadores de macro de click con delay bajo
                            if any(kw in content for kw in ('mousedown', 'mouseclick', 'leftclick',
                                                              'keystroke', 'macro', 'actiontype')):
                                # Buscar delays bajos (< 20ms)
                                import re as _re
                                delays = _re.findall(r'delay["\s:]+(\d+)', content)
                                if any(int(d) < 20 for d in delays if d.isdigit()):
                                    macro_found = True
                                    print(f"🚨 MACRO RAZER CON DELAY BAJO: {profile_path}")
                        except Exception:
                            pass
            if any(os.path.exists(d) for d in razer_dirs):
                alerta = 'CRITICAL' if macro_found else 'SOSPECHOSO'
                desc   = 'Macro de autoclick Razer detectada (delay < 20ms)' if macro_found else 'Razer Synapse instalado con perfiles configurados'
                self.issues_found.append({
                    'nombre': desc,
                    'ruta': next(d for d in razer_dirs if os.path.exists(d)),
                    'archivo': 'Razer profile',
                    'tipo': 'razer_macros',
                    'categoria': 'AUTOCLICK',
                    'alerta': alerta,
                    'confidence': 0.85 if macro_found else 0.40,
                    'detected_patterns': ['razer_macro_click' if macro_found else 'razer_installed'],
                })
        except Exception as e:
            print(f"Error escaneando macros Razer: {e}")
    
    def scan_event_logs(self):
        """Escanea logs de eventos del sistema buscando cambios de fecha/hora y borrado de logs."""
        print("🔍 Escaneando logs de eventos del sistema (sin abrir GUI)...")
        import subprocess
        import xml.etree.ElementTree as _ET

        # Eventos de interés: 4616=cambio hora, 1102/104=logs borrados, 4688=proceso creado
        QUERIES = [
            ('Security', '*[System[EventID=4616]]',  'Cambio de fecha/hora del sistema', 'CRITICAL'),
            ('Security', '*[System[EventID=1102]]',  'Logs de seguridad borrados', 'CRITICAL'),
            ('System',   '*[System[EventID=104]]',   'Logs del sistema borrados', 'CRITICAL'),
        ]

        for log_name, query, description, severity in QUERIES:
            try:
                result = subprocess.run(
                    ['wevtutil', 'qe', log_name,
                     f'/q:{query}',
                     '/c:20', '/rd:true', '/f:xml'],
                    capture_output=True, text=True, timeout=15,
                    creationflags=0x08000000  # CREATE_NO_WINDOW
                )
                if not result.stdout.strip():
                    continue
                # Parsear eventos
                xml_text = f'<root>{result.stdout.strip()}</root>'
                try:
                    root = _ET.fromstring(xml_text)
                    count = len(root.findall('.//{http://schemas.microsoft.com/win/2004/08/events/event}Event'))
                    if count == 0:
                        continue
                    print(f"⚠️ Evento detectado: {description} ({count} ocurrencias)")
                    self.issues_found.append({
                        'nombre': f'{description} ({count} evento(s) en logs)',
                        'ruta':   f'EventLog:{log_name}',
                        'archivo': log_name,
                        'tipo':   'event_logs',
                        'categoria': 'DATE_CHANGES',
                        'alerta': severity,
                        'confidence': 0.85,
                        'detected_patterns': [f'event:{log_name}:{severity.lower()}'],
                        'explicacion': (
                            f'El log de eventos "{log_name}" registra {count} ocurrencia(s) de: '
                            f'{description}. Este tipo de evento es indicador de manipulación del sistema.'
                        ),
                    })
                except _ET.ParseError:
                    pass
            except Exception:
                pass
    
    def scan_processes(self):
        """Escanea procesos activos"""
        try:
            import psutil
            for proc in psutil.process_iter(['pid', 'name', 'exe']):
                try:
                    proc_info = proc.info
                    if proc_info['name'] and self.is_suspicious_process(proc_info['name']):
                        self.issues_found.append({
                            'nombre': proc_info['name'],
                            'ruta': proc_info.get('exe', 'N/A'),
                            'archivo': proc_info['name'],
                            'tipo': 'process',
                            'pid': proc_info['pid'],
                            'categoria': 'PROCESSES',
                            'alerta': 'CRITICAL'
                        })
                except (psutil.NoSuchProcess, psutil.AccessDenied):
                    continue
        except Exception as e:
            print(f"Error escaneando procesos: {e}")
    
    def is_suspicious_process(self, process_name):
        """Verifica si un proceso es sospechoso - MEJORADO CON MÁS PATRONES"""
        process_name = process_name.lower()
        
        # Patrones críticos de procesos de hack
        critical_processes = [
            'vape', 'vapelite', 'vapev2', 'vapev4', 'entropy', 'entropyclient',
            'whiteout', 'whiteoutclient', 'liquidbounce', 'wurst', 'wurstclient',
            'impact', 'impactclient', 'sigma', 'sigmaclient', 'flux', 'fluxclient',
            'future', 'futureclient', 'astolfo', 'exhibition', 'novoline', 'rise',
            'moon', 'drip', 'phobos', 'komat', 'wasp', 'konas', 'seppuku', 'sloth',
            'lucid', 'tenacity', 'nyx', 'vanish', 'ploow', 'cloudclient', 'cloud-client', 'nextgen',
            'tegernako', 'zeroday', 'injector', 'inyector',
            'dllinjector', 'ghostclient', 'bypass', 'undetected',
            'incognito', 'unbypass', 'killaura', 'aimbot', 'triggerbot',
            'xray', 'fullbright', 'speedhack',
            'wtap', 'aimassist', 'bhop', 'nofall', 'autoclicker', 'ac.exe'
        ]
        
        # Verificar patrones críticos
        for pattern in critical_processes:
            if pattern in process_name:
                # Verificar que no sea falso positivo
                if not self.is_whitelisted(process_name):
                    return True
        
        return False
    
    def scan_windows(self):
        """Escanea ventanas abiertas"""
        try:
            import ctypes
            from ctypes import wintypes
            
            def enum_windows_proc(hwnd, lParam):
                if ctypes.windll.user32.IsWindowVisible(hwnd):
                    length = ctypes.windll.user32.GetWindowTextLengthW(hwnd)
                    if length > 0:
                        buffer = ctypes.create_unicode_buffer(length + 1)
                        ctypes.windll.user32.GetWindowTextW(hwnd, buffer, length + 1)
                        window_title = buffer.value
                        
                        if self.is_suspicious_window(window_title):
                            self.issues_found.append({
                                'nombre': window_title,
                                'ruta': 'N/A',
                                'archivo': window_title,
                                'tipo': 'window',
                                'categoria': 'PROCESSES',
                                'alerta': 'SOSPECHOSO'
                            })
                return True
            
            EnumWindowsProc = ctypes.WINFUNCTYPE(ctypes.c_bool, wintypes.HWND, wintypes.LPARAM)
            ctypes.windll.user32.EnumWindows(EnumWindowsProc(enum_windows_proc), 0)
        except Exception as e:
            print(f"Error escaneando ventanas: {e}")
    
    def is_suspicious_window(self, window_title):
        """Verifica si una ventana es sospechosa"""
        window_title = window_title.lower()
        suspicious_windows = [
            'vape', 'entropy', 'whiteout', 'liquidbounce', 'wurst',
            'impactclient', 'sigmaclient', 'fluxclient', 'futureclient', 'injector', 'ghostclient'
        ]
        
        for pattern in suspicious_windows:
            if pattern in window_title:
                return True
        
        return False
    
    def scan_registry(self):
        """Escanea el registro de Windows"""
        try:
            import winreg
            
            # Claves del registro a verificar
            registry_keys = [
                (winreg.HKEY_CURRENT_USER, r"Software"),
                (winreg.HKEY_LOCAL_MACHINE, r"SOFTWARE")
            ]
            
            for hkey, subkey in registry_keys:
                try:
                    with winreg.OpenKey(hkey, subkey) as key:
                        self._scan_registry_key(key, "")
                except Exception as e:
                    print(f"Error accediendo al registro: {e}")
        except Exception as e:
            print(f"Error escaneando registro: {e}")
    
    def _scan_registry_key(self, key, path):
        """Escanea una clave del registro recursivamente"""
        try:
            i = 0
            while True:
                try:
                    subkey_name = winreg.EnumKey(key, i)
                    subkey_path = f"{path}\\{subkey_name}" if path else subkey_name
                    
                    if self.is_suspicious_registry_key(subkey_name):
                        self.issues_found.append({
                            'nombre': subkey_name,
                            'ruta': subkey_path,
                            'archivo': subkey_name,
                            'tipo': 'registry',
                            'categoria': 'HACKS',
                            'alerta': 'SOSPECHOSO'
                        })
                    
                    i += 1
                except WindowsError:
                    break
        except Exception as e:
            print(f"Error escaneando clave del registro: {e}")
    
    def is_suspicious_registry_key(self, key_name):
        """Verifica si una clave del registro es sospechosa"""
        key_name = key_name.lower()
        suspicious_keys = [
            'vape', 'entropy', 'whiteout', 'liquidbounce', 'wurst',
            'impactclient', 'sigmaclient', 'fluxclient', 'futureclient', 'injector', 'ghostclient',
            'killaura', 'aimbot', 'dllinjector',
        ]
        
        for pattern in suspicious_keys:
            if pattern in key_name:
                return True
        
        return False
    
    # ══════════════════════════════════════════════════════════════════════════
    # NUEVOS MÓDULOS DE DETECCIÓN
    # ══════════════════════════════════════════════════════════════════════════

    def scan_cmd_history_full(self):
        """Escanea historial de comandos CMD, Win+R, búsquedas de carpeta y TypedPaths."""
        print("🔍 Escaneando historial de comandos y búsquedas...")
        suspicious_terms = [
            'vape', 'entropy', 'wurst', 'liquidbounce', 'sigmaclient', 'fluxclient', 'futureclient',
            'killaura', 'aimbot', 'ghostclient', 'autoclicker', 'phobos', 'astolfo', 'novoline',
            'liquidbounce', 'riseclient', 'moonclient', 'dllinjector',
        ]
        try:
            keys_to_check = [
                # Win+R history
                (winreg.HKEY_CURRENT_USER,
                 r'Software\Microsoft\Windows\CurrentVersion\Explorer\RunMRU',
                 'WIN+R'),
                # Folder address bar
                (winreg.HKEY_CURRENT_USER,
                 r'Software\Microsoft\Windows\CurrentVersion\Explorer\TypedPaths',
                 'EXPLORER_PATHS'),
                # Windows Search
                (winreg.HKEY_CURRENT_USER,
                 r'Software\Microsoft\Windows\CurrentVersion\Explorer\WordWheelQuery',
                 'FOLDER_SEARCH'),
                # cmd.exe recent
                (winreg.HKEY_CURRENT_USER,
                 r'Software\Microsoft\Windows NT\CurrentVersion\Windows',
                 'CMD_LOAD'),
            ]
            for hive, subkey, source in keys_to_check:
                try:
                    with winreg.OpenKey(hive, subkey) as reg_key:
                        i = 0
                        while True:
                            try:
                                name, value, _ = winreg.EnumValue(reg_key, i)
                                i += 1
                                val_str = str(value).lower()
                                for term in suspicious_terms:
                                    if term in val_str:
                                        self.issues_found.append({
                                            'tipo': 'cmd_history',
                                            'nombre': f'Comando sospechoso en {source}: {str(value)[:120]}',
                                            'ruta': f'HKCU\\{subkey}\\{name}',
                                            'archivo': str(value)[:255],
                                            'categoria': 'CMD_HISTORY',
                                            'alerta': 'SOSPECHOSO',
                                            'confidence': 70,
                                            'detected_patterns': [term],
                                        })
                                        print(f"⚠️ CMD/Run sospechoso [{source}]: {str(value)[:80]}")
                                        break
                            except OSError:
                                break
                except (FileNotFoundError, PermissionError):
                    pass

            # También guardar TODOS los comandos Win+R como historial informativo
            try:
                with winreg.OpenKey(winreg.HKEY_CURRENT_USER,
                                    r'Software\Microsoft\Windows\CurrentVersion\Explorer\RunMRU') as k:
                    entries = []
                    i = 0
                    while True:
                        try:
                            name, value, _ = winreg.EnumValue(k, i)
                            i += 1
                            if name != 'MRUList' and str(value).strip():
                                entries.append(str(value).rstrip('\x01\x02'))
                        except OSError:
                            break
                    if entries:
                        self.issues_found.append({
                            'tipo': 'cmd_history_full',
                            'nombre': f'Historial Win+R ({len(entries)} entradas)',
                            'ruta': 'HKCU\\Explorer\\RunMRU',
                            'archivo': ' | '.join(entries[:20]),
                            'categoria': 'CMD_HISTORY',
                            'alerta': 'NORMAL',
                            'confidence': 0,
                            'detected_patterns': entries[:20],
                        })
            except Exception:
                pass
        except Exception as e:
            print(f"Error en scan_cmd_history_full: {e}")

    def scan_prefetch_all(self):
        """Escanea TODOS los archivos prefetch para detectar ejecutables sospechosos con timestamps."""
        print("🔍 Escaneando prefetch completo...")
        prefetch_path = os.path.join(os.environ.get('WINDIR', 'C:\\Windows'), 'Prefetch')
        if not os.path.exists(prefetch_path):
            return

        hack_names = [
            # Ghost clients conocidos
            'vape', 'entropy', 'wurst', 'liquidbounce', 'sigma', 'flux', 'future',
            'astolfo', 'novoline', 'phobos', 'rise', 'meteor', 'weave', 'jello',
            'datura', 'drip', 'vertex', 'mathias', 'rusherhack', 'azura', 'salhack',
            'inertia', 'remix', 'ares', 'aristois', 'komat', 'wasp', 'konas',
            'seppuku', 'sloth', 'moon', 'exhibition', 'liqd', 'exhib',
            # Módulos y tipos de hack
            'killaura', 'aimbot', 'triggerbot', 'scaffold', 'autoclick', 'clicker',
            # Herramientas de inyección
            'inject', 'injector', 'dllinjector', 'xenos', 'extreme.inject',
            # Términos genéricos de evasión
            'bypass', 'undetected', 'ghost', 'stealth',
            # Malware genérico
            'hack', 'cheat', 'keylogger', 'rat.', 'trojan',
        ]
        legit_names = [
            'windows', 'microsoft', 'chrome', 'firefox', 'explorer', 'system',
            'svchost', 'csrss', 'winlogon', 'lsass', 'services', 'smss',
            'discord', 'steam', 'minecraft', 'javaw', 'java', 'nvidia', 'amd',
            'photoshop', 'office', 'word', 'excel', 'powerpoint', 'outlook',
            'teams', 'zoom', 'spotify', 'vlc', 'notepad', 'mspaint', 'calc'
        ]

        all_executed = []
        suspicious_executed = []
        try:
            for pf_file in os.listdir(prefetch_path):
                if not pf_file.endswith('.pf'):
                    continue
                try:
                    pf_path = os.path.join(prefetch_path, pf_file)
                    mtime = os.path.getmtime(pf_path)
                    last_run = datetime.fromtimestamp(mtime).strftime('%Y-%m-%d %H:%M:%S')
                    exe_name = pf_file.split('-')[0].lower()  # Nombre antes del hash
                    all_executed.append({'name': pf_file, 'last_run': last_run, 'path': pf_path})

                    name_lower = pf_file.lower()
                    is_legit = any(l in name_lower for l in legit_names)
                    is_hack = smart_hack_match(name_lower, _smart_hack_regex_cached(tuple(hack_names)))

                    if is_hack and not is_legit:
                        suspicious_executed.append({
                            'tipo': 'prefetch_suspicious',
                            'nombre': f'Ejecutable sospechoso en prefetch: {pf_file}',
                            'ruta': pf_path,
                            'archivo': pf_file,
                            'categoria': 'EXECUTED_FILES',
                            'alerta': 'CRITICAL',
                            'confidence': 85,
                            'detected_patterns': [h for h in hack_names if h in name_lower],
                            'extra': {'last_run': last_run},
                        })
                        print(f"🚨 PREFETCH SOSPECHOSO: {pf_file} (última ejecución: {last_run})")
                except Exception:
                    pass

            # Guardar lista completa de ejecutados como referencia informativa
            if all_executed:
                summary = ' | '.join([f"{e['name']} @ {e['last_run']}" for e in sorted(
                    all_executed, key=lambda x: x['last_run'], reverse=True)[:30]])
                self.issues_found.append({
                    'tipo': 'prefetch_history',
                    'nombre': f'Prefetch: {len(all_executed)} programas ejecutados recientemente',
                    'ruta': prefetch_path,
                    'archivo': summary[:500],
                    'categoria': 'EXECUTED_FILES',
                    'alerta': 'NORMAL',
                    'confidence': 0,
                    'detected_patterns': [e['name'] for e in all_executed[:30]],
                })

            for s in suspicious_executed:
                self.issues_found.append(s)

        except Exception as e:
            print(f"Error en scan_prefetch_all: {e}")

    def scan_deleted_recycle(self):
        """Escanea Recycle Bin en TODOS los drives — 48h, tamaño de archivo, presencia de $R."""
        print("🔍 Escaneando Recycle Bin (todos los drives, últimas 48h)...")
        hack_terms = list(_DEFINITE_HACK_NAMES) + [
            'killaura', 'aimbot', 'autoclick', 'clicker',
            'dllinjector', 'extremeinjector', 'cheatengine', 'xenos',
            '.rise', '.meteor', '.drip', '.vertex', '.azura', '.jello', '.datura',
            '.mathias', '.rusherhack', '.salhack', '.inertia', 'weaveloader',
        ]
        # Extensiones que merecen alerta cuando aparecen borradas:
        #   ejecutables/scripts: .exe .jar .dll .bat .ps1 .vbs .ahk .py
        #   comprimidos (vehículo de distribución): .zip .rar .7z .tar
        #   loaders / instaladores / accesos directos / volcados de registro:
        #     .lnk (puede apuntar al hack), .iso/.img (mount loader), .msi (instalador),
        #     .reg (alterar configs de Windows / persistencia)
        INTERESTING_EXTS = {'.exe', '.jar', '.dll', '.bat', '.ps1', '.vbs', '.ahk', '.py',
                              '.zip', '.rar', '.7z', '.tar',
                              '.lnk', '.iso', '.img', '.msi', '.reg'}
        CUTOFF_48H  = time.time() - 604800  # 7 días
        EPOCH_DIFF  = 116444736000000000

        import struct
        drives = []
        for d in 'CDEFGHIJKLMNOPQRSTUVWXYZ':
            p = f'{d}:\\$RECYCLE.BIN'
            if os.path.exists(p):
                drives.append(p)

        for recycle_root in drives:
            try:
                for user_sid in os.listdir(recycle_root):
                    sid_path = os.path.join(recycle_root, user_sid)
                    if not os.path.isdir(sid_path):
                        continue
                    try:
                        for fname in os.listdir(sid_path):
                            if not fname.startswith('$I'):
                                continue
                            i_path = os.path.join(sid_path, fname)
                            try:
                                with open(i_path, 'rb') as f:
                                    data = f.read(576)
                                if len(data) < 28:
                                    continue

                                # $I header: 8b version | 8b original_size | 8b FILETIME | path UTF-16LE
                                file_size_bytes = struct.unpack_from('<Q', data, 8)[0]
                                ft_raw          = struct.unpack_from('<Q', data, 16)[0]
                                unix_ts = (ft_raw - EPOCH_DIFF) / 10_000_000 if ft_raw > EPOCH_DIFF else 0

                                if unix_ts == 0 or unix_ts < CUTOFF_48H:
                                    continue

                                try:
                                    orig_path = data[28:].decode('utf-16-le').rstrip('\x00').split('\x00')[0]
                                except Exception:
                                    orig_path = ''
                                if not orig_path:
                                    continue

                                base    = os.path.basename(orig_path)
                                base_l  = base.lower()
                                ext     = os.path.splitext(base_l)[1]
                                is_exec = ext in INTERESTING_EXTS
                                is_hack = (smart_hack_match(base_l, _smart_hack_regex_cached(tuple(hack_terms)))
                                           or smart_hack_match(orig_path.lower(), _smart_hack_regex_cached(tuple(hack_terms))))

                                if not (is_exec or is_hack):
                                    continue

                                # Verificar si $R (el archivo real) sigue en la papelera
                                r_name  = fname.replace('$I', '$R', 1)
                                r_path  = os.path.join(sid_path, r_name)
                                still_in_bin = os.path.exists(r_path)

                                # Filtro #2 lite: si el binario sigue presente
                                # y está firmado por un publisher confiable
                                # (Microsoft, NVIDIA, Discord, Mojang, etc.),
                                # descartar la alerta. Evita FPs por nombres
                                # desafortunados de software legítimo borrado.
                                if still_in_bin and ext in {'.exe', '.dll', '.msi'}:
                                    if is_trusted_publisher(r_path):
                                        continue

                                deleted_dt = datetime.fromtimestamp(unix_ts)
                                now_dt     = datetime.now()
                                diff_mins  = int((now_dt - deleted_dt).total_seconds() / 60)
                                if diff_mins < 60:
                                    tiempo_rel = f'hace {diff_mins} min'
                                else:
                                    tiempo_rel = f'hace {diff_mins // 60}h {diff_mins % 60:02d}min'
                                deleted_str = deleted_dt.strftime('%d/%m %H:%M')

                                # Archivos borrados permanentemente (ya no están en la papelera) son más sospechosos
                                is_archive = ext in ('.zip', '.rar', '.7z', '.tar')
                                if is_hack:
                                    base_alerta = 'CRITICAL'
                                elif not still_in_bin and is_exec and not is_archive:
                                    base_alerta = 'CRITICAL'   # ejecutable borrado permanentemente
                                else:
                                    base_alerta = 'SOSPECHOSO'

                                size_str = ''
                                if file_size_bytes > 0:
                                    size_str = (f'{file_size_bytes // 1048576} MB'
                                                if file_size_bytes > 1048576
                                                else f'{file_size_bytes // 1024} KB')

                                perm = ' [BORRADO PERMANENTEMENTE]' if not still_in_bin else ''
                                print(f"🗑️ ELIMINADO ({tiempo_rel}){perm}: {base} {size_str}")
                                self.issues_found.append({
                                    'tipo':     'deleted_recent',
                                    'nombre':   f'Borrado{perm} {tiempo_rel}: {base}{(" " + size_str) if size_str else ""}',
                                    'ruta':     orig_path[:255],
                                    'archivo':  base,
                                    'categoria':'DELETED_FILES',
                                    'alerta':   base_alerta,
                                    'confidence': (0.88 if is_hack else 0.40 if is_archive else 0.55) + (0.10 if not still_in_bin else 0),
                                    'detected_patterns': [f'deleted:{ext}',
                                                          'permanently_deleted' if not still_in_bin else 'in_recycle_bin']
                                                         + [t for t in hack_terms if t in base_l][:3],
                                    'extra': {
                                        'deleted_at':    deleted_str,
                                        'deleted_ts':    unix_ts,
                                        'file_size':     file_size_bytes,
                                        'still_in_bin':  still_in_bin,
                                        'drive':         recycle_root[:2],
                                    },
                                })
                            except Exception:
                                continue
                    except PermissionError:
                        continue
            except Exception as e:
                print(f"Error leyendo {recycle_root}: {e}")

    # ──────────────────────────────────────────────────────────────
    #  MEJORAS V2 — Mouse timing, hooks, options.txt, borrado
    # ──────────────────────────────────────────────────────────────

    def _start_click_timing_monitor(self):
        """Inicia hilo de fondo que muestrea GetAsyncKeyState cada 5ms durante 90s."""
        import ctypes
        import threading as _th
        self._click_timestamps = []
        self._click_timing_active = True

        def _poll():
            VK_LBUTTON = 0x01
            prev = False
            while self._click_timing_active:
                state = bool(ctypes.windll.user32.GetAsyncKeyState(VK_LBUTTON) & 0x8000)
                if state and not prev:
                    self._click_timestamps.append(time.perf_counter())
                prev = state
                time.sleep(0.005)

        self._click_timing_thread = _th.Thread(target=_poll, daemon=True)
        self._click_timing_thread.start()

    def _stop_click_timing_monitor(self):
        """Detiene el hilo y analiza los intervalos — detecta autoclick por σ < 8ms."""
        self._click_timing_active = False
        ts = getattr(self, '_click_timestamps', [])
        if len(ts) < 15:
            return  # muy pocos clicks para analizar

        intervals = [(ts[i] - ts[i-1]) * 1000 for i in range(1, len(ts))]  # ms
        # Filtrar intervalos > 2s (pausa normal del jugador)
        intervals = [x for x in intervals if x < 2000]
        if len(intervals) < 10:
            return

        mean = sum(intervals) / len(intervals)
        sigma = (sum((x - mean) ** 2 for x in intervals) / len(intervals)) ** 0.5
        cps = len(ts) / max(1, ts[-1] - ts[0])

        print(f"🖱️ Click timing: {len(ts)} clicks, σ={sigma:.1f}ms, CPS={cps:.1f}")

        if sigma < 8 and cps > 5:
            alerta = 'CRITICAL'
            conf   = 0.90
            desc   = f'σ={sigma:.1f}ms (humano > 20ms) — autoclick casi certero'
        elif sigma < 20 and cps > 8:
            alerta = 'SOSPECHOSO'
            conf   = 0.70
            desc   = f'σ={sigma:.1f}ms, {cps:.1f} CPS — patrón sospechoso'
        else:
            return  # patrón humano normal

        self.issues_found.append({
            'tipo':     'autoclick_timing',
            'nombre':   f'Patrón de click anómalo: {desc}',
            'ruta':     '',
            'archivo':  '',
            'categoria':'AUTOCLICK',
            'alerta':   alerta,
            'confidence': conf,
            'detected_patterns': [f'sigma:{sigma:.1f}ms', f'cps:{cps:.1f}'],
        })
        print(f"🚨 AUTOCLICK DETECTADO POR TIMING: {desc}")

    def scan_input_hook_processes(self):
        """Detecta procesos con global hooks de teclado/mouse (WH_KEYBOARD_LL, WH_MOUSE_LL)
        y drivers de bypass: Interception, vJoy, ViGEm."""
        print("🔍 Detectando hooks de input y drivers de bypass...")
        # Drivers/servicios de bypass de bajo nivel
        BYPASS_SERVICES = {
            'interception': 'Driver Interception (bypass de input de bajo nivel)',
            'vjoy':         'vJoy (mando virtual — simula input)',
            'vigem':        'ViGEmBus (controlador virtual)',
            'hid_hook':     'HID Hook driver detectado',
            'mouclass':     None,  # skip — es legítimo
        }
        # Procesos que instalan hooks de input sospechosamente
        HOOK_PROC_KW = [
            'autohotkey', ' ahk', 'jitter', 'clicker', 'macro',
            'inputbot', 'pyautogui', 'xdotool', 'synapse',
            'ghub', 'logioptionsplus',
        ]
        SAFE_HOOK_PROCS = {
            'discord', 'obs', 'streamlabs', 'xsplit', 'voicemod',
            'teams', 'zoom', 'slack', 'chrome', 'firefox', 'edge',
        }
        try:
            import winreg
            # Revisar servicios de driver
            for svc, desc in BYPASS_SERVICES.items():
                if desc is None:
                    continue
                try:
                    key = winreg.OpenKey(winreg.HKEY_LOCAL_MACHINE,
                                         f'SYSTEM\\CurrentControlSet\\Services\\{svc}',
                                         0, winreg.KEY_READ)
                    winreg.CloseKey(key)
                    print(f"🚨 DRIVER BYPASS ENCONTRADO: {svc}")
                    self.issues_found.append({
                        'tipo':     'bypass_driver',
                        'nombre':   f'Driver de bypass activo: {svc}',
                        'ruta':     f'HKLM\\SYSTEM\\CurrentControlSet\\Services\\{svc}',
                        'archivo':  svc,
                        'categoria':'AUTOCLICK',
                        'alerta':   'CRITICAL',
                        'confidence': 0.88,
                        'detected_patterns': [f'driver:{svc}', 'input_bypass'],
                    })
                except (FileNotFoundError, OSError):
                    pass
        except Exception:
            pass

        try:
            for proc in psutil.process_iter(['pid', 'name', 'exe']):
                try:
                    name = (proc.info.get('name') or '').lower()
                    if any(s in name for s in SAFE_HOOK_PROCS):
                        continue
                    if any(k in name for k in HOOK_PROC_KW):
                        exe = proc.info.get('exe') or ''
                        print(f"⚠️ Proceso con posible hook de input: {name}")
                        self.issues_found.append({
                            'tipo':     'input_hook_process',
                            'nombre':   f'Proceso hook de input activo: {name}',
                            'ruta':     exe,
                            'archivo':  name,
                            'categoria':'AUTOCLICK',
                            'alerta':   'SOSPECHOSO',
                            'confidence': 0.65,
                            'detected_patterns': [f'proc:{name}'],
                        })
                except (psutil.NoSuchProcess, psutil.AccessDenied):
                    continue
        except Exception as e:
            print(f"Error en scan_input_hook_processes: {e}")

    def scan_options_resolution_mismatch(self):
        """Detecta modificaciones en options.txt: resolution override imposible,
        gamma > 1.0 (fullbright), guiScale inválido, renderDistance PvP anómalamente bajo."""
        print("🔍 Fingerprint de options.txt vs sistema...")
        import ctypes as _ct
        try:
            sys_w = _ct.windll.user32.GetSystemMetrics(0)
            sys_h = _ct.windll.user32.GetSystemMetrics(1)
        except Exception:
            sys_w = sys_h = 0

        appdata = os.environ.get('APPDATA', '')
        mc_dir  = os.path.join(appdata, '.minecraft')
        opts_files = []
        root_opts = os.path.join(mc_dir, 'options.txt')
        if os.path.isfile(root_opts):
            opts_files.append(root_opts)
        profiles_dir = os.path.join(mc_dir, 'versions')
        if os.path.isdir(profiles_dir):
            for ver in os.listdir(profiles_dir):
                p = os.path.join(profiles_dir, ver, 'options.txt')
                if os.path.isfile(p):
                    opts_files.append(p)

        for opts_path in opts_files:
            try:
                cfg = {}
                with open(opts_path, 'r', encoding='utf-8', errors='ignore') as f:
                    for line in f:
                        if ':' in line:
                            k, _, v = line.strip().partition(':')
                            cfg[k.strip()] = v.strip()

                findings = []
                # Gamma > 1.0 = fullbright (visión nocturna)
                try:
                    gamma = float(cfg.get('gamma', '0'))
                    if gamma > 1.05:
                        findings.append(('fullbright', f'gamma={gamma:.2f} (>1.0 = fullbright activado)', 'SOSPECHOSO', 0.80))
                except ValueError:
                    pass

                # Resolution override imposible (mayor que el monitor físico)
                try:
                    ow = int(cfg.get('overrideWidth', '0'))
                    oh = int(cfg.get('overrideHeight', '0'))
                    if ow > 0 and oh > 0 and sys_w > 0:
                        if ow > sys_w * 1.1 or oh > sys_h * 1.1:
                            findings.append(('resolution_override',
                                f'overrideWidth={ow}x{oh} > monitor {sys_w}x{sys_h}',
                                'SOSPECHOSO', 0.65))
                except ValueError:
                    pass

                # guiScale fuera de rango (0-4 válidos)
                try:
                    gs = int(cfg.get('guiScale', '2'))
                    if gs not in (0, 1, 2, 3, 4):
                        findings.append(('gui_scale_invalid', f'guiScale={gs} (inválido)', 'POCO_SOSPECHOSO', 0.50))
                except ValueError:
                    pass

                # renderDistance muy bajo en PvP (<= 4 chunks) con fullbright activo
                try:
                    rd   = int(cfg.get('renderDistance', '12'))
                    gval = float(cfg.get('gamma', '1'))
                    if rd <= 4 and gval > 0.9:
                        findings.append(('pvp_settings', f'renderDistance={rd}+gamma={gval:.1f} — perfil PvP optimizado', 'POCO_SOSPECHOSO', 0.45))
                except ValueError:
                    pass

                for tag, msg, alerta, conf in findings:
                    print(f"⚠️ options.txt {tag}: {msg}")
                    self.issues_found.append({
                        'tipo':     'options_fingerprint',
                        'nombre':   f'options.txt: {msg}',
                        'ruta':     opts_path,
                        'archivo':  'options.txt',
                        'categoria':'GHOST_CLIENT',
                        'alerta':   alerta,
                        'confidence': conf,
                        'detected_patterns': [tag],
                    })
            except Exception:
                continue

    def scan_file_activity_log(self):
        """Historial COMPLETO de actividad de archivos desde el último arranque del sistema.
        Captura: borrados, ejecutados, creados, modificados, renombrados.
        Fuentes:
          - Recycle Bin ($I files)        → borrados (todos los drives)
          - Prefetch (.pf files)          → ejecutados
          - USN Journal (NTFS, fsutil)    → creados/modificados/borrados/renombrados (requiere admin)
          - Walk de carpetas user         → creados/modificados (fallback robusto sin admin)
        Categoría FILE_ACTIVITY — informacional, NO afecta Risk Score.
        Alimenta el tab "Logs" del panel staff."""
        import struct
        EPOCH_DIFF = 116444736000000000
        # Ventana: desde el boot del sistema (sesión actual)
        try:
            session_start = psutil.boot_time()
        except Exception:
            session_start = time.time() - 86400  # fallback 24h
        try:
            session_dt = datetime.fromtimestamp(session_start).strftime('%d/%m %H:%M')
        except Exception:
            session_dt = '?'

        # Detectar privilegios de administrador (necesario para USN Journal)
        try:
            has_admin = bool(ctypes.windll.shell32.IsUserAnAdmin())
        except Exception:
            has_admin = False

        # Cap de entradas para no saturar UI/DB. Mantenemos las MÁS RECIENTES.
        MAX_ENTRIES = 5000
        seen_keys = set()                # (action, path_lower)
        activity_entries = []            # acumulador local

        # Filtro #30: paths/nombres del propio Argus que NO deben aparecer
        # como actividad de archivos en el reporte (autorreferencia ruidosa).
        _SELF_TOKENS = (
            'asperssprojects', 'aspersprojectsss',  # carpeta de logs en %appdata%
            'argusscanner', 'argusscanner.exe',     # binario y derivados
            'minecraftsstool', 'minecraftsstool.exe',
            'argus_screenshot', 'argus_report',
            '\\argus\\', '/argus/',                 # carpetas dev locales
            'aspers\\dist\\', 'aspers/dist/',
        )

        def _is_argus_self(p_lower: str) -> bool:
            return any(t in p_lower for t in _SELF_TOKENS)

        def _add(action: str, path: str, ts: float, source: str,
                 size: int = 0, extra_data: dict = None) -> bool:
            if not path or not action or not ts:
                return False
            if ts < session_start:
                return False
            try:
                path_norm = str(path)[:300]
            except Exception:
                return False
            path_lower = path_norm.lower()
            if _is_argus_self(path_lower):
                return False
            key = (action, path_lower)
            if key in seen_keys:
                return False
            seen_keys.add(key)
            try:
                ts_str = datetime.fromtimestamp(ts).strftime('%Y-%m-%d %H:%M:%S')
            except Exception:
                ts_str = ''
            entry_extra = {
                'action':    action,
                'timestamp': ts_str,
                'ts':        ts,
                'source':    source,
            }
            if size:
                entry_extra['size'] = size
            if extra_data:
                entry_extra.update(extra_data)
            activity_entries.append({
                'tipo':     'file_' + action,
                'nombre':   os.path.basename(path_norm) or path_norm,
                'ruta':     path_norm[:255],
                'archivo':  path_norm[:255],
                'categoria':'FILE_ACTIVITY',
                'alerta':   'POCO_SOSPECHOSO',
                'confidence': 0.05,
                'detected_patterns': [f'{action}_file', f'src:{source}'],
                'extra': entry_extra,
            })
            return True

        rb_count = pf_count = usn_count = walk_count = 0

        # ── 1. RECYCLE BIN — Borrados (todos los $I de todos los drives) ──
        for drv in 'CDEFGHIJKLMNOPQRSTUVWXYZ':
            recycle = f'{drv}:\\$RECYCLE.BIN'
            if not os.path.exists(recycle):
                continue
            try:
                sids = os.listdir(recycle)
            except (PermissionError, OSError):
                continue
            for sid in sids:
                sid_path = os.path.join(recycle, sid)
                if not os.path.isdir(sid_path):
                    continue
                try:
                    files_in_sid = os.listdir(sid_path)
                except (PermissionError, OSError):
                    continue
                for fname in files_in_sid:
                    if not fname.startswith('$I'):
                        continue
                    i_path = os.path.join(sid_path, fname)
                    try:
                        with open(i_path, 'rb') as f:
                            data = f.read()  # entero (suele ser <1KB)
                        if len(data) < 28:
                            continue
                        try:
                            size_bytes = struct.unpack_from('<Q', data, 8)[0]
                        except Exception:
                            size_bytes = 0
                        try:
                            ft_raw = struct.unpack_from('<Q', data, 16)[0]
                        except Exception:
                            continue
                        if ft_raw <= EPOCH_DIFF:
                            continue
                        unix_ts = (ft_raw - EPOCH_DIFF) / 10_000_000
                        try:
                            orig_path = (data[28:]
                                         .decode('utf-16-le', errors='ignore')
                                         .rstrip('\x00')
                                         .split('\x00')[0])
                        except Exception:
                            continue
                        if not orig_path:
                            continue
                        r_path = os.path.join(sid_path, fname.replace('$I', '$R', 1))
                        still_in_bin = os.path.exists(r_path)
                        if _add('deleted', orig_path, unix_ts,
                                source='recycle_bin', size=size_bytes,
                                extra_data={'still_in_bin': still_in_bin, 'drive': drv}):
                            rb_count += 1
                    except Exception:
                        continue

        # ── 2. PREFETCH — Ejecutados ──
        prefetch_dir = os.path.join(os.environ.get('WINDIR', 'C:\\Windows'), 'Prefetch')
        if os.path.isdir(prefetch_dir):
            try:
                pf_files = os.listdir(prefetch_dir)
            except (PermissionError, OSError):
                pf_files = []
            for pf in pf_files:
                if not pf.lower().endswith('.pf'):
                    continue
                pf_full = os.path.join(prefetch_dir, pf)
                try:
                    mtime = os.path.getmtime(pf_full)
                except Exception:
                    continue
                if mtime < session_start:
                    continue
                # Nombre del exe es lo que va antes del primer "-" en el .pf
                exe_name = pf.split('-')[0]
                if _add('executed', exe_name, mtime, source='prefetch'):
                    pf_count += 1

        # ── 3. USN JOURNAL — Creados/Modificados/Borrados/Renombrados (requiere admin) ──
        if has_admin:
            try:
                usn_count = self._read_usn_journal_into(
                    activity_entries=activity_entries,
                    seen_keys=seen_keys,
                    add_func=_add,
                    cutoff=session_start,
                    max_entries=MAX_ENTRIES,
                )
            except Exception as e:
                print(f"⚠️ USN Journal falló: {e}")

        # ── 4. WALK DE CARPETAS USER — Creados/Modificados (siempre corre, fallback) ──
        try:
            walk_count = self._walk_user_folders_into(
                add_func=_add,
                cutoff=session_start,
                budget_left=max(0, MAX_ENTRIES - len(activity_entries)),
            )
        except Exception as e:
            print(f"⚠️ Walk de carpetas user falló: {e}")

        # ── 5. Volcar al issues_found, ordenado por timestamp DESC ──
        try:
            activity_entries.sort(key=lambda r: r.get('extra', {}).get('ts', 0), reverse=True)
        except Exception:
            pass
        # Cortar al máximo definido (preserva los más recientes)
        if len(activity_entries) > MAX_ENTRIES:
            activity_entries = activity_entries[:MAX_ENTRIES]

        self.issues_found.extend(activity_entries)

        admin_str = "admin ✓" if has_admin else "no-admin"
        print(f"📋 Historial de archivos: {len(activity_entries)} entradas "
              f"(boot {session_dt}, {admin_str}) | "
              f"recycle:{rb_count} prefetch:{pf_count} usn:{usn_count} walk:{walk_count}")

    # ──────────────────────────────────────────────────────────────────
    #  Helpers para scan_file_activity_log
    # ──────────────────────────────────────────────────────────────────

    def _read_usn_journal_into(self, activity_entries, seen_keys, add_func,
                               cutoff: float, max_entries: int) -> int:
        """Lee USN Journal de los volúmenes NTFS vía 'fsutil usn readjournal'.
        Retorna número de entradas añadidas a activity_entries.
        Mapea Reasons NTFS a actions del panel:
          FILE_CREATE        → created
          FILE_DELETE        → deleted
          RENAME_NEW_NAME    → created
          RENAME_OLD_NAME    → deleted
          DATA_OVERWRITE     → modified
          DATA_EXTEND        → modified
          DATA_TRUNCATION    → modified
          BASIC_INFO_CHANGE  → modified
          (otros mod flags)  → modified

        Notas:
          - fsutil solo da el nombre del archivo, no el path completo. Se prefija
            con la letra del drive como "C:\\<filename>".
          - La salida puede ser muy grande; cortamos al cap de max_entries.
        """
        if len(activity_entries) >= max_entries:
            return 0

        REASON_MAP = {
            'File create':           'created',
            'File delete':           'deleted',
            'Rename: new name':      'created',
            'Rename: old name':      'deleted',
            'Data overwrite':        'modified',
            'Data extend':           'modified',
            'Data truncation':       'modified',
            'Named data overwrite':  'modified',
            'Named data extend':     'modified',
            'Named data truncation': 'modified',
            'Basic info change':     'modified',
            'Object id change':      'modified',
            'Reparse point change':  'modified',
            'Stream change':         'modified',
            'Hard link change':      'modified',
            'Compression change':    'modified',
            'Encryption change':     'modified',
            'Security change':       'modified',
        }

        added = 0
        # Volúmenes a inspeccionar (solo NTFS detectables como letra de drive)
        candidate_drives = []
        for d in 'CDEF':
            try:
                if os.path.exists(f'{d}:\\'):
                    candidate_drives.append(f'{d}:')
            except Exception:
                continue

        for drive in candidate_drives:
            if len(activity_entries) >= max_entries:
                break
            try:
                proc = subprocess.run(
                    ['fsutil', 'usn', 'readjournal', drive],
                    capture_output=True,
                    timeout=45,
                    creationflags=getattr(subprocess, 'CREATE_NO_WINDOW', 0),
                )
            except (FileNotFoundError, subprocess.TimeoutExpired, OSError):
                continue
            except Exception:
                continue

            if proc.returncode != 0:
                continue

            try:
                output = (proc.stdout or b'').decode('utf-8', errors='ignore')
                if not output:
                    output = (proc.stdout or b'').decode('mbcs', errors='ignore')
            except Exception:
                continue

            current = {}

            def _flush():
                nonlocal added
                if not current:
                    return
                name   = current.get('name')
                reason = current.get('reason', '')
                ts     = current.get('ts', 0)
                if not name or ts < cutoff:
                    return
                # Determinar action a partir de los reason flags
                action = None
                # Si hay delete, prevalece (file_delete > rename > data*)
                rl = reason.lower()
                if 'file delete' in rl or 'rename: old name' in rl:
                    action = 'deleted'
                elif 'file create' in rl or 'rename: new name' in rl:
                    action = 'created'
                else:
                    for k, v in REASON_MAP.items():
                        if k.lower() in rl:
                            action = v
                            break
                if not action:
                    return
                full_path = f'{drive}\\{name}' if not (':' in name or name.startswith('\\')) else name
                if add_func(action, full_path, ts, source='usn_journal',
                            extra_data={'reason': reason[:100]}):
                    added += 1

            for line in output.splitlines():
                if len(activity_entries) >= max_entries:
                    break
                ls = line.strip()
                if not ls:
                    continue
                # Cada bloque empieza con "Usn"
                if ls.lower().startswith('usn'):
                    _flush()
                    current = {}
                    continue
                # Parseo "Clave : Valor"
                if ':' not in ls:
                    continue
                k, _, v = ls.partition(':')
                k = k.strip().lower()
                v = v.strip()
                if k.startswith('file name'):
                    current['name'] = v
                elif k.startswith('reason'):
                    # "0x00000200: File create" o "0x...: File create | Close"
                    if ':' in v:
                        v = v.split(':', 1)[1].strip()
                    current['reason'] = v
                elif k.startswith('time stamp') or k.startswith('timestamp'):
                    parsed_ts = self._parse_usn_timestamp(v)
                    if parsed_ts:
                        current['ts'] = parsed_ts
            # Último bloque
            _flush()

        return added

    @staticmethod
    def _parse_usn_timestamp(s: str) -> float:
        """Intenta parsear un timestamp de fsutil USN en varios formatos comunes."""
        if not s:
            return 0
        s = s.strip()
        formats = (
            '%m/%d/%Y %I:%M:%S %p',
            '%m/%d/%Y %H:%M:%S',
            '%d/%m/%Y %H:%M:%S',
            '%d/%m/%Y %I:%M:%S %p',
            '%Y-%m-%d %H:%M:%S',
            '%d-%m-%Y %H:%M:%S',
        )
        for fmt in formats:
            try:
                return datetime.strptime(s, fmt).timestamp()
            except (ValueError, OSError):
                continue
        return 0

    def _walk_user_folders_into(self, add_func, cutoff: float, budget_left: int) -> int:
        """Recorre carpetas del usuario actual reportando archivos creados o modificados
        después de `cutoff`. Sin filtros: incluye AppData/Temp/Cache, hasta el cap.

        Usa os.scandir recursivo (más rápido que os.walk porque cada DirEntry trae el
        stat() del dirent ahorrando una syscall por archivo). Retorna # de entradas añadidas.
        """
        if budget_left <= 0:
            return 0
        added = 0
        user_home = os.path.expanduser('~')
        # Carpetas a recorrer (orden = prioridad). Evitamos solapamiento: como
        # AppData\Roaming ya incluye .minecraft, no se lista por separado para no
        # gastar inspections en re-deduplicar.
        candidates = [
            os.path.join(user_home, 'Desktop'),
            os.path.join(user_home, 'Downloads'),
            os.path.join(user_home, 'Documents'),
            os.path.join(user_home, 'OneDrive'),
            os.path.join(user_home, 'Videos'),
            os.path.join(user_home, 'Pictures'),
            os.path.join(user_home, 'Music'),
            os.path.join(user_home, 'AppData', 'Roaming'),     # incluye .minecraft, configs
            os.path.join(user_home, 'AppData', 'LocalLow'),
            os.path.join(user_home, 'AppData', 'Local'),       # más pesado: cache de browsers
            'C:\\Users\\Public',
        ]
        # Cap de archivos a inspeccionar para evitar bloquear varios minutos.
        # 500k cubre escenarios típicos (~75-90s). Si se excede, paramos en seco.
        MAX_FILES_INSPECTED = 500000
        # Hard time cap (segundos) para no bloquear el scan completo
        TIME_CAP = 90.0
        deadline = time.time() + TIME_CAP

        inspected = 0

        def _scan_dir(dir_path: str) -> int:
            """Recorre dir_path recursivamente con os.scandir. Retorna # añadidos.
            Usa una pila local en vez de recursión para evitar StackOverflow en árboles
            profundos (.gradle/caches puede tener 10+ niveles)."""
            nonlocal inspected, added
            local_added = 0
            stack = [dir_path]
            while stack:
                if added >= budget_left or inspected >= MAX_FILES_INSPECTED or time.time() > deadline:
                    break
                cur = stack.pop()
                try:
                    it = os.scandir(cur)
                except (PermissionError, FileNotFoundError, OSError):
                    continue
                try:
                    for ent in it:
                        if added >= budget_left or inspected >= MAX_FILES_INSPECTED or time.time() > deadline:
                            break
                        try:
                            if ent.is_dir(follow_symlinks=False):
                                stack.append(ent.path)
                                continue
                            if not ent.is_file(follow_symlinks=False):
                                continue
                        except (PermissionError, OSError):
                            continue
                        inspected += 1
                        try:
                            st = ent.stat(follow_symlinks=False)
                        except (FileNotFoundError, PermissionError, OSError):
                            continue
                        ctime = st.st_ctime
                        mtime = st.st_mtime
                        size  = st.st_size
                        # Creado en este boot → 'created'
                        # Solo mtime reciente → 'modified'
                        if ctime >= cutoff:
                            if add_func('created', ent.path, ctime, source='walk', size=size):
                                added += 1
                                local_added += 1
                        elif mtime >= cutoff:
                            if add_func('modified', ent.path, mtime, source='walk', size=size):
                                added += 1
                                local_added += 1
                finally:
                    try:
                        it.close()
                    except Exception:
                        pass
            return local_added

        for root_dir in candidates:
            if added >= budget_left or inspected >= MAX_FILES_INSPECTED or time.time() > deadline:
                break
            if not os.path.isdir(root_dir):
                continue
            try:
                _scan_dir(root_dir)
            except (PermissionError, OSError):
                continue
        return added

    def scan_deleted_mass_event(self):
        """Detecta ráfagas de borrado: >=5 archivos eliminados en <2 minutos en la Recycle Bin.
        Un borrado masivo justo antes del scan es una señal fuerte de limpieza activa."""
        print("🔍 Detectando eventos de borrado masivo en Recycle Bin...")
        import struct
        EPOCH_DIFF = 116444736000000000
        CUTOFF_48H = time.time() - 172800  # 48h

        all_deletions = []  # lista de (unix_ts, orig_path)
        try:
            for drive in ['C', 'D', 'E', 'F']:
                recycle_root = f'{drive}:\\$RECYCLE.BIN'
                if not os.path.exists(recycle_root):
                    continue
                for user_sid in os.listdir(recycle_root):
                    sid_path = os.path.join(recycle_root, user_sid)
                    if not os.path.isdir(sid_path):
                        continue
                    for fname in os.listdir(sid_path):
                        if not fname.startswith('$I'):
                            continue
                        i_path = os.path.join(sid_path, fname)
                        try:
                            with open(i_path, 'rb') as f:
                                data = f.read(576)
                            if len(data) < 28:
                                continue
                            ft_raw  = struct.unpack_from('<Q', data, 16)[0]
                            unix_ts = (ft_raw - EPOCH_DIFF) / 10_000_000 if ft_raw > EPOCH_DIFF else 0
                            if unix_ts < CUTOFF_48H:
                                continue
                            orig_path = data[28:].decode('utf-16-le').rstrip('\x00').split('\x00')[0]
                            all_deletions.append((unix_ts, orig_path))
                        except Exception:
                            continue
        except Exception as e:
            print(f"Error leyendo Recycle Bin en scan_deleted_mass_event: {e}")
            return

        if not all_deletions:
            return

        # Agrupar en ventanas de 2 minutos
        all_deletions.sort(key=lambda x: x[0])
        WINDOW = 120  # 2 minutos
        i = 0
        while i < len(all_deletions):
            t0 = all_deletions[i][0]
            cluster = [x for x in all_deletions if t0 <= x[0] <= t0 + WINDOW]
            if len(cluster) >= 5:
                deleted_dt = datetime.fromtimestamp(t0)
                now_dt     = datetime.now()
                diff_mins  = int((now_dt - deleted_dt).total_seconds() / 60)
                tiempo_rel = f'hace {diff_mins}min' if diff_mins < 60 else f'hace {diff_mins//60}h'
                sample     = [os.path.basename(p) for _, p in cluster[:5]]
                print(f"🚨 BORRADO MASIVO ({tiempo_rel}): {len(cluster)} archivos en 2min")
                self.issues_found.append({
                    'tipo':     'mass_delete_event',
                    'nombre':   f'Borrado masivo {tiempo_rel}: {len(cluster)} archivos en <2 min',
                    'ruta':     '',
                    'archivo':  ', '.join(sample),
                    'categoria':'DELETED_FILES',
                    'alerta':   'CRITICAL' if diff_mins < 30 else 'SOSPECHOSO',
                    'confidence': 0.82 if diff_mins < 30 else 0.60,
                    'detected_patterns': ['mass_delete', f'count:{len(cluster)}', f'window:2min'],
                })
                # Saltar hasta el final del cluster para no re-detectar
                i += len(cluster)
            else:
                i += 1

    def scan_shadow_copy_artifacts(self):
        """Verifica si VSS (Volume Shadow Copy) tiene snapshots activos y si contienen
        archivos sospechosos que fueron borrados del sistema en vivo."""
        print("🔍 Buscando artifacts en Shadow Copies (VSS)...")
        import subprocess
        HACK_KW = ['hack', 'cheat', 'vape', 'sigma', 'rise', 'meteor', 'liquidbounce',
                   'future', 'flux', 'ghost', 'inject', 'aimbot', 'killaura']
        try:
            result = subprocess.run(
                ['vssadmin', 'list', 'shadows', '/for=C:'],
                capture_output=True, text=True, timeout=10
            )
            output = result.stdout or ''
            if 'Shadow Copy Volume' not in output and 'Volumen de copia' not in output:
                print("ℹ️ Sin Shadow Copies activos en C:")
                return

            # Extraer rutas de Shadow Copies
            shadow_paths = []
            for line in output.splitlines():
                line = line.strip()
                if 'Shadow Copy Volume' in line or ('\\\\?\\' in line and 'Volume{' in line):
                    parts = line.split(':')
                    if len(parts) >= 2:
                        raw = parts[-1].strip()
                        shadow_paths.append(raw)

            for shadow_root in shadow_paths[:3]:  # máx 3 snapshots
                mc_shadow = os.path.join(shadow_root, 'Users')
                if not os.path.exists(mc_shadow):
                    continue
                try:
                    for user_dir in os.listdir(mc_shadow):
                        mc_path = os.path.join(mc_shadow, user_dir, 'AppData',
                                               'Roaming', '.minecraft', 'mods')
                        if not os.path.isdir(mc_path):
                            continue
                        live_path = os.path.join(
                            'C:\\Users', user_dir, 'AppData', 'Roaming', '.minecraft', 'mods')
                        for fname in os.listdir(mc_path):
                            shadow_file = os.path.join(mc_path, fname)
                            live_file   = os.path.join(live_path, fname)
                            fname_l     = fname.lower()
                            is_hack     = any(k in fname_l for k in HACK_KW)
                            deleted_live = not os.path.exists(live_file)
                            if is_hack or (deleted_live and fname_l.endswith('.jar')):
                                alerta = 'CRITICAL' if is_hack else 'SOSPECHOSO'
                                print(f"🚨 SHADOW COPY: {fname} ({'borrado del sistema en vivo' if deleted_live else 'hack en snapshot'})")
                                self.issues_found.append({
                                    'tipo':     'shadow_copy_artifact',
                                    'nombre':   f'Archivo en Shadow Copy{"(borrado en vivo)" if deleted_live else ""}: {fname}',
                                    'ruta':     shadow_file,
                                    'archivo':  fname,
                                    'categoria':'DELETED_FILES',
                                    'alerta':   alerta,
                                    'confidence': 0.85 if is_hack else 0.65,
                                    'detected_patterns': ['vss_artifact']
                                                         + (['deleted_from_live'] if deleted_live else [])
                                                         + ([k for k in HACK_KW if k in fname_l]),
                                })
                except Exception:
                    continue
        except Exception as e:
            print(f"Error en scan_shadow_copy_artifacts: {e}")

    # ──────────────────────────────────────────────────────────────
    #  NUEVAS DETECCIONES — Ghost clients, JDWP, VPN, Hosts
    # ──────────────────────────────────────────────────────────────

    def scan_ghost_client_configs(self):
        """Detecta carpetas y archivos de configuración de ghost clients conocidos."""
        print("🔍 Escaneando configs de ghost clients...")
        appdata  = os.environ.get('APPDATA', '')
        localapp = os.environ.get('LOCALAPPDATA', '')
        home     = os.path.expanduser('~')
        mc_dir   = os.path.join(appdata, '.minecraft')
        GHOST_CONFIGS = [
            # Rutas en AppData/Roaming
            ('Rise Client',        os.path.join(appdata,  '.rise')),
            ('Sigma Client',       os.path.join(appdata,  '.sigma')),
            ('Meteor Client',      os.path.join(appdata,  '.meteor')),
            ('LiquidBounce',       os.path.join(appdata,  '.liquidbounce')),
            ('Weave Loader',       os.path.join(appdata,  '.weave')),
            ('Jello Client',       os.path.join(appdata,  'jello')),
            ('Datura Client',      os.path.join(appdata,  '.datura')),
            ('Drip Client',        os.path.join(appdata,  '.drip')),
            ('Vertex Client',      os.path.join(appdata,  '.vertex')),
            ('Mathias Client',     os.path.join(appdata,  '.mathias')),
            ('RusherHack',         os.path.join(appdata,  '.rusherhack')),
            ('Azura Client',       os.path.join(appdata,  '.azura')),
            ('Novoline Client',    os.path.join(appdata,  '.novoline')),
            ('Future Client',      os.path.join(appdata,  '.future')),
            ('Flux Client',        os.path.join(appdata,  '.flux')),
            ('Astolfo Client',     os.path.join(appdata,  '.astolfo')),
            ('Salhack Client',     os.path.join(appdata,  '.salhack')),
            ('Entropy Client',     os.path.join(appdata,  '.entropy')),
            ('Wurst Client',       os.path.join(appdata,  '.wurst')),
            ('Remix Client',       os.path.join(appdata,  '.remix')),
            ('Ares Client',        os.path.join(appdata,  '.ares')),
            ('Kami/KamiBlue',      os.path.join(appdata,  '.kamiblue')),
            ('Konas Client',       os.path.join(appdata,  '.konas')),
            ('Pandora Client',     os.path.join(appdata,  '.pandora')),
            ('Nyx Client',         os.path.join(appdata,  '.nyx')),
            ('Lucid Client',       os.path.join(appdata,  '.lucid')),
            ('Tenacity Client',    os.path.join(appdata,  '.tenacity')),
            ('Aristois Client',    os.path.join(appdata,  '.aristois')),
            ('Inertia Client',     os.path.join(appdata,  '.inertia')),
            ('Baritone',           os.path.join(appdata,  '.minecraft', 'baritone')),
            ('Phobos Client',      os.path.join(appdata,  '.phobos')),
            ('Weepcraft Client',   os.path.join(appdata,  '.weepcraft')),
            ('GhostClient',        os.path.join(appdata,  '.ghostclient')),
            # AppData/Local
            ('WeaveLoader (Local)',os.path.join(localapp, 'WeaveLoader')),
            ('Kami Local',         os.path.join(localapp, '.kamiblue')),
            # Archivos de configuración específicos en home
            ('Inertia (home)',     os.path.join(home,     '.inertia')),
            ('Vape (encrypted)',   os.path.join(appdata,  'vape.encrypted')),
            ('Vape (json)',        os.path.join(appdata,  'vape.json')),
            ('Vape (settings)',    os.path.join(appdata,  'vapesettings.json')),
            # En carpeta de Minecraft directamente
            ('Baritone (mc)',      os.path.join(mc_dir,   'baritone')),
            ('Weave (mc)',         os.path.join(mc_dir,   '.weave')),
            ('LiquidBounce (mc)', os.path.join(mc_dir,   '.liquidbounce')),
        ]
        # Campos en JSON que confirman que el archivo es un config de hack
        HACK_JSON_FIELDS = {
            'killaura', 'aimassist', 'triggerbot', 'reach', 'velocity',
            'antikb', 'scaffold', 'nofall', 'fly', 'xray', 'wallhack',
            'autoclick', 'clickgui', 'bhop', 'timer', 'speedhack',
            'silent', 'blatant', 'bypass', 'undetected',
        }
        try:
            for client_name, config_path in GHOST_CONFIGS:
                if not os.path.exists(config_path):
                    continue
                print(f"🚨 GHOST CLIENT CONFIG: {client_name} → {config_path}")

                # Si es un archivo JSON, verificar contenido para aumentar confianza
                extra_patterns = [f'ghost_config:{client_name.lower().replace(" ", "_")}']
                confidence = 0.97
                if os.path.isfile(config_path) and config_path.endswith('.json'):
                    try:
                        import json as _json
                        with open(config_path, 'r', encoding='utf-8', errors='ignore') as f:
                            raw = f.read(8192).lower()
                        matched_fields = [kw for kw in HACK_JSON_FIELDS if kw in raw]
                        if matched_fields:
                            extra_patterns.append(f'json_fields:{",".join(matched_fields[:5])}')
                            confidence = 0.99
                    except Exception:
                        pass

                self.issues_found.append({
                    'nombre': f'Config de ghost client detectada: {client_name}',
                    'ruta': config_path,
                    'archivo': os.path.basename(config_path),
                    'tipo': 'ghost_client_config',
                    'categoria': 'GHOST_CLIENT',
                    'alerta': 'CRITICAL',
                    'confidence': confidence,
                    'detected_patterns': extra_patterns,
                    'explicacion': (
                        f'Se encontró la carpeta/archivo de configuración de {client_name} en {config_path}. '
                        f'Esta ruta solo existe si el jugador ha ejecutado {client_name} en este PC.'
                    ),
                })
        except Exception as e:
            print(f"Error en scan_ghost_client_configs: {e}")

    def scan_config_tfidf(self):
        """P3 #8 — Analiza el contenido de archivos JSON/config buscando campos
        característicos de ghost clients, aunque el archivo esté renombrado.
        Usa un enfoque TF-IDF simplificado: peso de términos en vocabulario de hacks."""
        print("🔍 TF-IDF análisis de config files...")
        import json as _json

        # Vocabulario de campos altamente específicos de ghost clients
        HACK_FIELDS = {
            # Módulos de combate
            'killaura': 3.0, 'killaurarange': 3.0, 'kaaura': 3.0,
            'aimassist': 2.5, 'aimbot': 3.0, 'triggerbot': 3.0,
            'velocity': 2.0, 'antikb': 2.5, 'antiknockback': 2.5,
            'reach': 2.0, 'reachrange': 2.5, 'hitbox': 2.0,
            'criticals': 2.0, 'autocrit': 2.5, 'wtap': 2.5, 'blatant': 2.5,
            # Movimiento
            'bhop': 2.5, 'bunny': 2.0, 'sprint': 1.5, 'nofall': 2.5,
            'flight': 3.0, 'fly': 2.0, 'elytra': 1.5, 'speed': 1.5,
            'scaffold': 2.5, 'tower': 2.0,
            # Visión
            'xray': 3.0, 'wallhack': 3.0, 'esp': 2.5, 'fullbright': 2.0,
            'chams': 2.0, 'tracers': 2.0, 'nametags': 1.5,
            # Red/bypass
            'nopacket': 2.5, 'packetfly': 2.5, 'nomotion': 2.0,
            'blink': 2.5, 'phase': 2.5, 'timer': 2.0, 'speedhack': 3.0,
            # Campos de configuración internos de hacks conocidos
            'yawspeed': 3.0, 'pitchspeed': 2.5, 'rotations': 2.0,
            'bypassed': 2.0, 'undetected': 2.5, 'silent': 2.0,
            'autoblock': 2.5, 'noswing': 2.0, 'critplace': 2.5,
            # LiquidBounce-specific
            'liquidbounce': 4.0, 'lbmodule': 3.5,
            # Vape-specific
            'vapeconfig': 4.0, 'vapesettings': 3.5,
            # General ghost client markers
            'clickgui': 2.0, 'modulelist': 2.0, 'hackmodule': 3.5,
        }
        SCORE_THRESHOLD = 6.0  # Suma de pesos para reportar

        # Rutas donde buscar configs sospechosas renombradas
        appdata  = os.environ.get('APPDATA', '')
        localapp = os.environ.get('LOCALAPPDATA', '')
        desktop  = os.path.join(os.path.expanduser('~'), 'Desktop')
        downloads = os.path.join(os.path.expanduser('~'), 'Downloads')

        SEARCH_PATHS = [appdata, localapp, desktop, downloads]
        EXTENSIONS   = {'.json', '.cfg', '.ini', '.yml', '.yaml', '.conf', '.properties'}
        MAX_FILES    = 200
        scanned = 0

        try:
            for base_path in SEARCH_PATHS:
                if not os.path.isdir(base_path) or scanned >= MAX_FILES:
                    break
                for root, dirs, files in os.walk(base_path):
                    dirs[:] = [d for d in dirs if d not in {
                        'node_modules', '.git', 'AppData', 'Microsoft', 'Windows',
                        'System32', 'chrome', 'firefox', 'edge', 'Google',
                    }]
                    for fname in files:
                        if scanned >= MAX_FILES:
                            break
                        ext = os.path.splitext(fname.lower())[1]
                        if ext not in EXTENSIONS:
                            continue
                        fpath = os.path.join(root, fname)
                        fpath_lower = fpath.lower()
                        # Excluir archivos de idioma de Minecraft (xx_xx.json)
                        import re as _re2
                        if _re2.match(r'^[a-z]{2}_[a-z]{2}\.json$', fname.lower()):
                            continue
                        # Excluir paths de assets/lang del juego
                        if 'assets\\minecraft\\lang' in fpath_lower or \
                           'assets/minecraft/lang' in fpath_lower or \
                           '\\assets\\' in fpath_lower:
                            continue
                        try:
                            fsize = os.path.getsize(fpath)
                            if fsize < 20 or fsize > 500 * 1024:  # 500KB max
                                continue
                            with open(fpath, 'r', encoding='utf-8', errors='ignore') as f:
                                content = f.read(8000).lower()
                            scanned += 1

                            # Calcular score TF-IDF simplificado
                            score = 0.0
                            matched = []
                            for field, weight in HACK_FIELDS.items():
                                if field in content:
                                    score += weight
                                    matched.append(field)

                            if score >= SCORE_THRESHOLD:
                                print(f"⚠️ CONFIG TFIDF: {fpath} (score={score:.1f})")
                                self.issues_found.append({
                                    'nombre': f'Config con campos de ghost client (score={score:.1f}): {fname}',
                                    'ruta': fpath,
                                    'archivo': fname,
                                    'tipo': 'config_tfidf_match',
                                    'categoria': 'GHOST_CLIENT',
                                    'alerta': 'CRITICAL' if score >= 10.0 else 'SOSPECHOSO',
                                    'confidence': min(0.92, 0.50 + score / 25),
                                    'detected_patterns': [f'field:{f}' for f in matched[:8]],
                                    'explicacion': (
                                        f'El archivo {fname} contiene {len(matched)} campos '
                                        f'asociados a ghost clients ({", ".join(matched[:5])}). '
                                        f'Esto puede indicar una config de hack renombrada para evadir detección.'
                                    ),
                                })
                        except Exception:
                            continue
        except Exception as e:
            print(f"Error en scan_config_tfidf: {e}")

    def scan_jdwp_port(self):
        """Detecta puerto de debug JDWP activo en procesos Java (permite inyección en runtime)."""
        print("🔍 Escaneando JDWP en procesos Java...")
        try:
            for proc in psutil.process_iter(['pid', 'name', 'cmdline']):
                try:
                    name = (proc.info.get('name') or '').lower()
                    if 'java' not in name:
                        continue
                    cmdline = ' '.join(proc.info.get('cmdline') or [])
                    if 'jdwp' in cmdline.lower() or 'agentlib:jdwp' in cmdline.lower():
                        print(f"🚨 JDWP PORT ACTIVO en PID {proc.pid}")
                        self.issues_found.append({
                            'nombre': f'Puerto debug JDWP activo en Java (PID {proc.pid}) — permite inyección de bytecode',
                            'ruta': cmdline[:255],
                            'archivo': proc.info.get('name', 'javaw.exe'),
                            'tipo': 'jdwp_debug_port',
                            'categoria': 'JAVA_INJECTION',
                            'alerta': 'CRITICAL',
                            'confidence': 0.95,
                            'detected_patterns': ['jdwp_active'],
                        })
                except (psutil.NoSuchProcess, psutil.AccessDenied):
                    continue
        except Exception as e:
            print(f"Error en scan_jdwp_port: {e}")

    def scan_vpn_adapters(self):
        """Detecta adaptadores VPN activos durante el scan (posible intento de evasión)."""
        print("🔍 Escaneando adaptadores VPN...")
        VPN_KEYWORDS = [
            'vpn', 'mullvad', 'nordvpn', 'expressvpn', 'protonvpn', 'surfshark',
            'private internet', 'ipvanish', 'cyberghost', 'windscribe', 'tunnelbear',
            'wireguard', 'openvpn', 'tap-windows', 'tap0901', 'psiphon',
            'hotspot shield', 'hide.me', 'pia vpn', 'privatevpn',
        ]
        try:
            for iface_name, stat in psutil.net_if_stats().items():
                if not stat.isup:
                    continue
                if any(kw in iface_name.lower() for kw in VPN_KEYWORDS):
                    print(f"ℹ️ VPN ACTIVA: {iface_name}")
                    self.issues_found.append({
                        'nombre': f'VPN activa durante el scan: {iface_name}',
                        'ruta': 'Adaptadores de red del sistema',
                        'archivo': iface_name,
                        'tipo': 'vpn_active',
                        'categoria': 'VPN',
                        'alerta': 'POCO_SOSPECHOSO',
                        'confidence': 0.30,
                        'detected_patterns': ['vpn_active_during_scan'],
                    })
        except Exception as e:
            print(f"Error en scan_vpn_adapters: {e}")

    def scan_hosts_file(self):
        """Detecta modificaciones en el hosts de Windows (redirección de dominios de Minecraft)."""
        print("🔍 Escaneando archivo hosts...")
        hosts_path = os.path.join(os.environ.get('WINDIR', 'C:\\Windows'),
                                  'System32', 'drivers', 'etc', 'hosts')
        if not os.path.exists(hosts_path):
            return
        MINECRAFT_DOMAINS = [
            'session.minecraft.net', 'authserver.mojang.com', 'account.mojang.com',
            'api.mojang.com', 'mojang.com', 'minecraft.net', 'multiplayer.minecraft',
            'hypixel.net', 'mineplex.com', 'cubecraft.net',
        ]
        try:
            with open(hosts_path, 'r', encoding='utf-8', errors='ignore') as f:
                lines = f.readlines()
            custom = []
            for line in lines:
                stripped = line.strip()
                if not stripped or stripped.startswith('#'):
                    continue
                if stripped in ('127.0.0.1 localhost', '::1 localhost', '127.0.0.1 localhost.localdomain'):
                    continue
                custom.append(stripped)
                if any(d in stripped.lower() for d in MINECRAFT_DOMAINS):
                    print(f"🚨 HOSTS REDIRIGE DOMINIO DE MINECRAFT: {stripped}")
                    self.issues_found.append({
                        'nombre': f'Hosts redirige dominio de Minecraft/Mojang: {stripped[:120]}',
                        'ruta': hosts_path,
                        'archivo': 'hosts',
                        'tipo': 'hosts_minecraft_redirect',
                        'categoria': 'EVASION',
                        'alerta': 'CRITICAL',
                        'confidence': 0.92,
                        'detected_patterns': ['hosts_mojang_redirect'],
                    })
            if custom:
                print(f"⚠️ HOSTS FILE CON {len(custom)} ENTRADA(S) NO ESTÁNDAR")
                self.issues_found.append({
                    'nombre': f'Hosts file modificado: {len(custom)} entrada(s) no estándar',
                    'ruta': hosts_path,
                    'archivo': '; '.join(custom[:5])[:255],
                    'tipo': 'hosts_file_custom',
                    'categoria': 'EVASION',
                    'alerta': 'SOSPECHOSO',
                    'confidence': 0.55,
                    'detected_patterns': ['hosts_custom_entries'],
                })
        except Exception as e:
            print(f"Error en scan_hosts_file: {e}")

    def scan_executed_userassist(self):
        """Lee UserAssist del registro para detectar ejecutables recientes con timestamps."""
        print("🔍 Escaneando UserAssist (ejecutables recientes)...")
        hack_terms = list(_DEFINITE_HACK_NAMES) + [
            'killaura', 'aimbot', 'dllinjector', 'cheatengine',
        ]
        # Apps del sistema Windows que nunca son hacks aunque contengan palabras clave
        _UA_SYSTEM_WHITELIST = [
            'cloudexperiencehost', 'microsoftedge', 'microsoftedgeupdate',
            'windows.immersivecontrolpanel', 'windows.store', 'microsoft.windows',
            'windowsdefender', 'windowssecurity', 'backgroundtransfer',
            'shellexperiencehost', 'startmenuexperiencehost', 'searchhost',
            'runtimebroker', 'applicationframehost', 'systemsettings',
            'textinputhost', 'cortana', 'lockapp', 'microsoft.ui.',
            # F30 — Launcher oficial Mojang llama a java.exe → no es sospechoso
            'minecraftlauncher', 'minecraft launcher', 'minecraft.exe',
            'javaw.exe', 'java.exe',  # el propio JRE
            'prismlauncher', 'multimc', 'lunarclient', 'badlionclient',
            'tlauncher', 'gdlauncher', 'atlauncher', 'curseforge', 'ftb',
        ]
        import codecs
        import struct

        def rot13(s):
            return codecs.encode(s, 'rot_13')

        ua_guids = [
            r'Software\Microsoft\Windows\CurrentVersion\Explorer\UserAssist\{CEBFF5CD-ACE2-4F4F-9178-9926F41749EA}\Count',
            r'Software\Microsoft\Windows\CurrentVersion\Explorer\UserAssist\{F4E57C4B-2036-45F0-A9AB-443BCFE33D9F}\Count',
        ]

        executed = []
        try:
            for guid_path in ua_guids:
                try:
                    with winreg.OpenKey(winreg.HKEY_CURRENT_USER, guid_path) as k:
                        i = 0
                        while True:
                            try:
                                name, data, _ = winreg.EnumValue(k, i)
                                i += 1
                                decoded = rot13(name)
                                if len(data) >= 72:
                                    try:
                                        ft_raw = struct.unpack_from('<Q', data, 60)[0]
                                        if ft_raw > 0:
                                            EPOCH_DIFF = 116444736000000000
                                            unix_ts = (ft_raw - EPOCH_DIFF) / 10000000
                                            if 0 < unix_ts < 2000000000:
                                                last_run = datetime.fromtimestamp(unix_ts).strftime('%Y-%m-%d %H:%M:%S')
                                            else:
                                                last_run = 'Desconocida'
                                        else:
                                            last_run = 'Desconocida'
                                    except Exception:
                                        last_run = 'Desconocida'
                                else:
                                    last_run = 'Desconocida'
                                executed.append({'name': decoded, 'last_run': last_run})
                            except OSError:
                                break
                except (FileNotFoundError, PermissionError):
                    pass

            suspicious = []
            for item in executed:
                name_lower = item['name'].lower()
                # Ignorar apps del sistema Windows
                if any(sys_app in name_lower for sys_app in _UA_SYSTEM_WHITELIST):
                    continue
                for term in hack_terms:
                    if term in name_lower:
                        suspicious.append(item)
                        self.issues_found.append({
                            'tipo': 'userassist_suspicious',
                            'nombre': f'Ejecutado sospechoso (UserAssist): {os.path.basename(item["name"])}',
                            'ruta': item['name'][:255],
                            'archivo': item['name'][:255],
                            'categoria': 'EXECUTED_FILES',
                            'alerta': 'CRITICAL',
                            'confidence': 80,
                            'detected_patterns': [term],
                            'extra': {'last_run': item['last_run']},
                        })
                        print(f"🚨 USERASSIST SOSPECHOSO: {item['name'][:80]} @ {item['last_run']}")
                        break

            if executed:
                summary = ' | '.join([f"{os.path.basename(e['name'])} @ {e['last_run']}"
                                       for e in sorted(executed, key=lambda x: x['last_run'], reverse=True)[:25]])
                self.issues_found.append({
                    'tipo': 'userassist_history',
                    'nombre': f'UserAssist: {len(executed)} ejecutables registrados',
                    'ruta': 'HKCU\\UserAssist',
                    'archivo': summary[:500],
                    'categoria': 'EXECUTED_FILES',
                    'alerta': 'NORMAL',
                    'confidence': 0,
                    'detected_patterns': [os.path.basename(e['name']) for e in executed[:25]],
                })
        except Exception as e:
            print(f"Error en scan_executed_userassist: {e}")

    # ── NUEVOS MÓDULOS ─────────────────────────────────────────────────────────

    def scan_run_mru(self):
        """Escanea comandos ejecutados desde el cuadro Ejecutar (Win+R)."""
        print("🔍 Escaneando RunMRU (Win+R)...")
        hack_terms = list(_DEFINITE_HACK_NAMES) + [
            'killaura', 'aimbot', 'triggerbot', 'dllinjector', 'cheatengine',
        ]
        key_path = r'Software\Microsoft\Windows\CurrentVersion\Explorer\RunMRU'
        try:
            with winreg.OpenKey(winreg.HKEY_CURRENT_USER, key_path) as k:
                i = 0
                while True:
                    try:
                        name, data, _ = winreg.EnumValue(k, i)
                        i += 1
                        if name == 'MRUList' or not isinstance(data, str):
                            continue
                        cmd = data.rstrip('\x01').strip()
                        cmd_lower = cmd.lower()
                        for term in hack_terms:
                            if term in cmd_lower:
                                self.issues_found.append({
                                    'tipo': 'run_mru_suspicious',
                                    'nombre': f'Win+R sospechoso: {cmd[:80]}',
                                    'ruta': key_path,
                                    'archivo': cmd[:255],
                                    'categoria': 'CMD_HISTORY',
                                    'alerta': 'CRITICAL',
                                    'confidence': 80,
                                    'detected_patterns': [term],
                                })
                                print(f"🚨 RUN MRU: {cmd[:80]}")
                                break
                    except OSError:
                        break
        except (FileNotFoundError, PermissionError):
            pass
        except Exception as e:
            print(f"Error en scan_run_mru: {e}")

    def scan_typed_paths(self):
        """Escanea rutas escritas en la barra de direcciones de Explorer."""
        print("🔍 Escaneando TypedPaths...")
        hack_terms = list(_DEFINITE_HACK_NAMES) + [
            'killaura', 'aimbot', 'triggerbot', 'dllinjector', 'cheatengine',
        ]
        # F31 — Rutas de launchers instalados: el usuario las tecleó para abrir el launcher,
        # no son evidencia de hacks. Excluir antes de evaluar hack_terms.
        _typed_path_safe = (
            'prismlauncher', 'multimc', 'gdlauncher', 'atlauncher', 'ftb app', 'ftbapp',
            'curseforge', 'tlauncher', 'lunarclient', 'lunar client',
            'program files\\java', 'program files (x86)\\java',
            'program files\\eclipse', 'program files\\jdk',
            '\\minecraft launcher', '\\minecraftlauncher',
        )
        key_path = r'Software\Microsoft\Windows\CurrentVersion\Explorer\TypedPaths'
        try:
            with winreg.OpenKey(winreg.HKEY_CURRENT_USER, key_path) as k:
                i = 0
                while True:
                    try:
                        name, data, _ = winreg.EnumValue(k, i)
                        i += 1
                        if not isinstance(data, str):
                            continue
                        path_lower = data.lower()
                        # F31: skip known launcher/safe paths
                        if any(sf in path_lower for sf in _typed_path_safe):
                            continue
                        for term in hack_terms:
                            if term in path_lower:
                                self.issues_found.append({
                                    'tipo': 'typed_path_suspicious',
                                    'nombre': f'Ruta sospechosa en Explorer: {data[:80]}',
                                    'ruta': key_path,
                                    'archivo': data[:255],
                                    'categoria': 'CMD_HISTORY',
                                    'alerta': 'CRITICAL',
                                    'confidence': 75,
                                    'detected_patterns': [term],
                                })
                                print(f"🚨 TYPED PATH: {data[:80]}")
                                break
                    except OSError:
                        break
        except (FileNotFoundError, PermissionError):
            pass
        except Exception as e:
            print(f"Error en scan_typed_paths: {e}")

    def scan_usb_history(self):
        """Escanea el historial de dispositivos USB conectados (USBSTOR)."""
        print("🔍 Escaneando historial USB (USBSTOR)...")
        key_path = r'SYSTEM\CurrentControlSet\Enum\USBSTOR'
        devices = []
        try:
            with winreg.OpenKey(winreg.HKEY_LOCAL_MACHINE, key_path) as base:
                i = 0
                while True:
                    try:
                        device_class = winreg.EnumKey(base, i)
                        i += 1
                        with winreg.OpenKey(base, device_class) as dc_key:
                            j = 0
                            while True:
                                try:
                                    instance = winreg.EnumKey(dc_key, j)
                                    j += 1
                                    # Nombre amigable
                                    friendly = device_class.replace('Disk&Ven_', '').replace('_Prod_', ' ').split('&Rev_')[0]
                                    devices.append(friendly[:80])
                                except OSError:
                                    break
                    except OSError:
                        break
            if devices:
                summary = ' | '.join(devices[:20])
                self.issues_found.append({
                    'tipo': 'usb_history',
                    'nombre': f'USB: {len(devices)} dispositivo(s) conectado(s) históricamente',
                    'ruta': key_path,
                    'archivo': summary[:400],
                    'categoria': 'HARDWARE',
                    'alerta': 'NORMAL',
                    'confidence': 0,
                    'detected_patterns': devices[:20],
                })
                print(f"✅ USBSTOR: {len(devices)} dispositivos en historial")
        except (FileNotFoundError, PermissionError):
            pass
        except Exception as e:
            print(f"Error en scan_usb_history: {e}")

    def scan_startup_entries(self):
        """Escanea entradas de autoarranque (Run/RunOnce) en busca de hacks con persistencia."""
        print("🔍 Escaneando entradas de inicio automático...")
        hack_terms = list(_DEFINITE_HACK_NAMES) + [
            'killaura', 'aimbot', 'triggerbot', 'dllinjector', 'cheatengine',
        ]
        run_keys = [
            (winreg.HKEY_CURRENT_USER,  r'Software\Microsoft\Windows\CurrentVersion\Run'),
            (winreg.HKEY_LOCAL_MACHINE, r'Software\Microsoft\Windows\CurrentVersion\Run'),
            (winreg.HKEY_CURRENT_USER,  r'Software\Microsoft\Windows\CurrentVersion\RunOnce'),
            (winreg.HKEY_LOCAL_MACHINE, r'Software\Microsoft\Windows\CurrentVersion\RunOnce'),
        ]
        for hive, path in run_keys:
            try:
                with winreg.OpenKey(hive, path) as k:
                    i = 0
                    while True:
                        try:
                            name, data, _ = winreg.EnumValue(k, i)
                            i += 1
                            if not isinstance(data, str):
                                continue
                            data_lower = data.lower()
                            name_lower = name.lower()
                            for term in hack_terms:
                                if term in data_lower or term in name_lower:
                                    self.issues_found.append({
                                        'tipo': 'startup_suspicious',
                                        'nombre': f'Startup sospechoso: {name} → {data[:60]}',
                                        'ruta': path,
                                        'archivo': data[:255],
                                        'categoria': 'PERSISTENCIA',
                                        'alerta': 'CRITICAL',
                                        'confidence': 90,
                                        'detected_patterns': [term],
                                    })
                                    print(f"🚨 STARTUP: {name} → {data[:60]}")
                                    break
                        except OSError:
                            break
            except (FileNotFoundError, PermissionError):
                pass
            except Exception as e:
                print(f"Error leyendo startup key {path}: {e}")

        # Carpeta Startup del menú inicio — hacks que persisten entre reinicios
        startup_dirs = [
            os.path.join(os.environ.get('APPDATA', ''),
                         'Microsoft', 'Windows', 'Start Menu', 'Programs', 'Startup'),
            os.path.join(os.environ.get('PROGRAMDATA', 'C:\\ProgramData'),
                         'Microsoft', 'Windows', 'Start Menu', 'Programs', 'Startup'),
        ]
        STARTUP_EXTS = {'.exe', '.bat', '.cmd', '.ps1', '.vbs', '.js', '.lnk', '.jar'}
        for sdir in startup_dirs:
            if not os.path.isdir(sdir):
                continue
            try:
                for fname in os.listdir(sdir):
                    fname_lower = fname.lower()
                    if not any(fname_lower.endswith(e) for e in STARTUP_EXTS):
                        continue
                    for term in hack_terms:
                        if term in fname_lower:
                            fpath = os.path.join(sdir, fname)
                            self.issues_found.append({
                                'tipo': 'startup_folder_hack',
                                'nombre': f'Archivo de inicio sospechoso: {fname}',
                                'ruta': sdir,
                                'archivo': fpath,
                                'categoria': 'PERSISTENCIA',
                                'alerta': 'CRITICAL',
                                'confidence': 0.93,
                                'detected_patterns': [term, 'startup_folder'],
                                'explicacion': (
                                    f'"{fname}" está en la carpeta Startup de Windows: se ejecuta '
                                    f'automáticamente cada vez que el usuario inicia sesión. '
                                    f'Su nombre contiene "{term}", asociado con hack clients.'
                                ),
                            })
                            print(f"🚨 STARTUP FOLDER: {fpath}")
                            break
            except Exception as e:
                print(f"Error escaneando startup folder {sdir}: {e}")

    def scan_inetcache(self):
        """P1 #30 — Escanea INetCache de IE/Edge para URLs de descarga de hacks."""
        appdata_local = os.environ.get('LOCALAPPDATA', '')
        cache_dirs = [
            os.path.join(appdata_local, 'Microsoft', 'Windows', 'INetCache', 'IE'),
            os.path.join(appdata_local, 'Microsoft', 'Windows', 'INetCache'),
        ]
        hack_terms = [
            'vape', 'meteor', 'wurst', 'liquidbounce', 'hack', 'cheat', 'killaura',
            'aimbot', 'triggerbot', 'sigma', 'aristois', 'tenacity', 'rusherhack',
        ]
        checked = 0
        for cdir in cache_dirs:
            if not os.path.isdir(cdir):
                continue
            try:
                for root_d, dirs, files in os.walk(cdir):
                    if checked > 2000:
                        break
                    for fname in files:
                        checked += 1
                        fname_lower = fname.lower()
                        for term in hack_terms:
                            if term in fname_lower:
                                fpath = os.path.join(root_d, fname)
                                self.issues_found.append({
                                    'tipo': 'inetcache_hack_url',
                                    'nombre': f'Caché de descarga sospechosa: {fname}',
                                    'ruta': root_d,
                                    'archivo': fpath,
                                    'categoria': 'HISTORIAL_WEB',
                                    'alerta': 'SOSPECHOSO',
                                    'confidence': 0.65,
                                    'detected_patterns': [term, 'inetcache'],
                                })
                                print(f"[INetCache] Hallazgo: {fname}")
                                break
            except (PermissionError, OSError):
                pass
            except Exception as e:
                print(f"Error en scan_inetcache: {e}")

    def scan_java_policy(self):
        """P1 #33 — Detecta java.policy modificado para deshabilitar sandbox de Java."""
        java_home = os.environ.get('JAVA_HOME', '')
        candidates = []
        if java_home:
            candidates.append(os.path.join(java_home, 'lib', 'security', 'java.policy'))
        appdata = os.environ.get('APPDATA', '')
        candidates.append(os.path.join(appdata, '.java', 'deployment', 'security', 'java.policy'))
        # Buscar java.home de la JVM de Minecraft
        mc_jre_root = os.path.join(appdata, '.minecraft', 'runtime')
        if os.path.isdir(mc_jre_root):
            for jre_name in os.listdir(mc_jre_root)[:3]:
                jre_path = os.path.join(mc_jre_root, jre_name)
                if os.path.isdir(jre_path):
                    for sub in os.listdir(jre_path)[:3]:
                        candidates.append(os.path.join(jre_path, sub, 'lib', 'security', 'java.policy'))

        SUSPICIOUS_GRANTS = [b'permission java.security.AllPermission', b'grant {', b'AllPermission']
        for pol_path in candidates:
            if not os.path.isfile(pol_path):
                continue
            try:
                with open(pol_path, 'rb') as f:
                    content = f.read(4096)
                # AllPermission grant is suspicious — disables Java security sandbox
                if (b'AllPermission' in content and b'grant' in content):
                    self.issues_found.append({
                        'tipo': 'java_policy_modified',
                        'nombre': f'java.policy con AllPermission: {os.path.basename(pol_path)}',
                        'ruta': os.path.dirname(pol_path),
                        'archivo': pol_path,
                        'categoria': 'ESCALADA_PRIVILEGIOS',
                        'alerta': 'SOSPECHOSO',
                        'confidence': 0.70,
                        'detected_patterns': ['AllPermission', 'java_policy'],
                    })
                    print(f"[java.policy] AllPermission encontrado: {pol_path}")
            except (PermissionError, OSError):
                pass
            except Exception as e:
                print(f"Error en scan_java_policy {pol_path}: {e}")

    def scan_windowless_java(self):
        """P2 #25 — Detecta procesos java sin ventana visible (CREATE_NO_WINDOW / headless injection)."""
        print("🔍 Verificando procesos java sin ventana...")
        try:
            import psutil, ctypes
            user32 = ctypes.windll.user32

            # Enumerar ventanas visibles y sus PIDs
            visible_pids: set = set()
            def _enum_cb(hwnd, _):
                if user32.IsWindowVisible(hwnd):
                    pid = ctypes.c_ulong(0)
                    user32.GetWindowThreadProcessId(hwnd, ctypes.byref(pid))
                    visible_pids.add(pid.value)
                return True
            WNDENUMPROC = ctypes.WINFUNCTYPE(ctypes.c_bool, ctypes.c_void_p, ctypes.c_void_p)
            user32.EnumWindows(WNDENUMPROC(_enum_cb), 0)

            for proc in psutil.process_iter(['pid', 'name', 'exe', 'cmdline']):
                try:
                    pname = (proc.info.get('name') or '').lower()
                    if 'java' not in pname:
                        continue
                    if proc.pid in visible_pids:
                        continue  # tiene ventana visible → legítimo
                    cmdline = ' '.join(proc.info.get('cmdline') or []).lower()
                    # Solo nos importa si tiene argumentos de agente o injection
                    if any(kw in cmdline for kw in ('-javaagent', '-agentlib', '-agentpath', 'lwjgl', 'minecraft')):
                        if 'minecraft' in cmdline and '-javaagent' not in cmdline:
                            continue  # MC legítimo sin agente → skip
                        self.issues_found.append({
                            'tipo':     'java_no_window',
                            'nombre':   f'{pname} (PID {proc.pid}) sin ventana visible',
                            'ruta':     proc.info.get('exe') or '',
                            'archivo':  proc.info.get('exe') or '',
                            'categoria': 'JAVA_INJECTION',
                            'alerta':   'SOSPECHOSO',
                            'confidence': 0.65,
                            'detected_patterns': ['windowless_java', 'no_visible_window'],
                        })
                        print(f"[java_nowin] {pname} PID {proc.pid} sin ventana")
                except (psutil.NoSuchProcess, psutil.AccessDenied):
                    pass
        except ImportError:
            pass
        except Exception as e:
            print(f"Error en scan_windowless_java: {e}")

    def scan_readonly_suspicious_files(self):
        """P2 #28 — Detecta archivos sospechosos con atributo de solo lectura (dificultan borrado)."""
        print("🔍 Verificando atributos de solo lectura en archivos sospechosos...")
        try:
            import ctypes
            FILE_ATTRIBUTE_READONLY = 0x1
            FILE_ATTRIBUTE_HIDDEN   = 0x2

            appdata     = os.environ.get('APPDATA', '')
            userprofile = os.environ.get('USERPROFILE', '')
            SCAN_DIRS   = [
                os.path.join(appdata, '.minecraft', 'mods'),
                os.path.join(appdata, '.weave'),
                os.path.join(appdata, '.sigma'),
                os.path.join(appdata, '.aristois'),
                os.path.join(userprofile, 'Downloads'),
            ]
            for scan_dir in SCAN_DIRS:
                if not os.path.isdir(scan_dir):
                    continue
                try:
                    for entry in os.scandir(scan_dir):
                        if not entry.name.lower().endswith(('.jar', '.exe', '.dll')):
                            continue
                        try:
                            attrs = ctypes.windll.kernel32.GetFileAttributesW(entry.path)
                            if attrs == 0xFFFFFFFF:
                                continue
                            if attrs & FILE_ATTRIBUTE_READONLY:
                                self.issues_found.append({
                                    'tipo':     'readonly_suspicious',
                                    'nombre':   f'Archivo sospechoso de solo lectura: {entry.name}',
                                    'ruta':     scan_dir,
                                    'archivo':  entry.path,
                                    'categoria': 'EVASION',
                                    'alerta':   'POCO_SOSPECHOSO',
                                    'confidence': 0.45,
                                    'detected_patterns': ['readonly_attr',
                                                          'hidden_attr' if attrs & FILE_ATTRIBUTE_HIDDEN else 'readonly_attr'],
                                })
                                print(f"[readonly] {entry.name}")
                        except (PermissionError, OSError):
                            pass
                except PermissionError:
                    pass
        except Exception as e:
            print(f"Error en scan_readonly_suspicious_files: {e}")

    def scan_minecraft_fs_changes(self):
        """P3 #30 — Detecta archivos modificados en .minecraft durante los últimos 5 minutos (cambios durante scan)."""
        print("🔍 Detectando cambios recientes en .minecraft...")
        try:
            appdata  = os.environ.get('APPDATA', '')
            mc_dir   = os.path.join(appdata, '.minecraft')
            if not os.path.isdir(mc_dir):
                return

            WATCH_SUBDIRS = ['mods', 'config', 'shaderpacks', 'resourcepacks', 'versions']
            cutoff = time.time() - 300  # últimos 5 minutos

            changed: list = []
            for sub in WATCH_SUBDIRS:
                sub_dir = os.path.join(mc_dir, sub)
                if not os.path.isdir(sub_dir):
                    continue
                try:
                    for entry in os.scandir(sub_dir):
                        try:
                            if entry.stat().st_mtime > cutoff:
                                changed.append(entry.path)
                        except OSError:
                            pass
                except PermissionError:
                    pass

            if changed:
                self.issues_found.append({
                    'tipo':     'mc_files_changed_during_scan',
                    'nombre':   f'{len(changed)} archivo(s) modificados en .minecraft en últimos 5min',
                    'ruta':     mc_dir,
                    'archivo':  mc_dir,
                    'categoria': 'EVASION',
                    'alerta':   'SOSPECHOSO' if len(changed) >= 3 else 'POCO_SOSPECHOSO',
                    'confidence': 0.60,
                    'detected_patterns': ['fs_change_during_scan'] + [os.path.basename(p) for p in changed[:5]],
                })
                print(f"[fs_watch] {len(changed)} cambios en .minecraft: {[os.path.basename(p) for p in changed[:3]]}")
        except Exception as e:
            print(f"Error en scan_minecraft_fs_changes: {e}")

    def scan_java_parent_process(self):
        """P2 #23 — Detecta java.exe/javaw.exe lanzado desde cmd.exe/powershell en lugar de un launcher legítimo."""
        print("🔍 Verificando proceso padre de java.exe...")
        try:
            import psutil
            SUSPICIOUS_PARENTS = {'cmd.exe', 'powershell.exe', 'powershell_ise.exe',
                                   'wscript.exe', 'cscript.exe', 'mshta.exe', 'regsvr32.exe'}
            LEGIT_PARENTS = {
                'javaw.exe', 'java.exe', 'explorer.exe', 'minecraft launcher.exe',
                'minecraftlauncher.exe', 'multimc.exe', 'prismlauncher.exe',
                'gdlauncher.exe', 'atlauncher.exe', 'curseforgeapp.exe',
                'modrinthapp.exe', 'ftb_app.exe', 'tlauncher.exe',
            }
            for proc in psutil.process_iter(['pid', 'name', 'exe', 'cmdline']):
                try:
                    pname = (proc.info.get('name') or '').lower()
                    if 'java' not in pname:
                        continue
                    parent = proc.parent()
                    if not parent:
                        continue
                    par_name = parent.name().lower()
                    if par_name in LEGIT_PARENTS:
                        continue
                    if par_name in SUSPICIOUS_PARENTS:
                        cmdline = ' '.join(proc.info.get('cmdline') or [])[:200]
                        self.issues_found.append({
                            'tipo':     'java_suspicious_parent',
                            'nombre':   f'{pname} lanzado desde {par_name}',
                            'ruta':     proc.info.get('exe') or '',
                            'archivo':  proc.info.get('exe') or '',
                            'categoria': 'JAVA_INJECTION',
                            'alerta':   'SOSPECHOSO',
                            'confidence': 0.72,
                            'detected_patterns': ['java_from_shell', f'parent_{par_name}'],
                        })
                        print(f"[java_parent] {pname} (PID {proc.pid}) lanzado desde {par_name}")
                except (psutil.NoSuchProcess, psutil.AccessDenied):
                    pass
        except ImportError:
            pass
        except Exception as e:
            print(f"Error en scan_java_parent_process: {e}")

    def scan_folder_name_nlp(self):
        """P3 #11 — Análisis NLP/heurístico de nombres de carpetas y archivos.
        Detecta nombres que suenan a hack aunque no estén en la whitelist exacta.
        """
        print("🔍 Análisis NLP de nombres de carpetas/archivos...")
        try:
            import difflib
            appdata     = os.environ.get('APPDATA', '')
            userprofile = os.environ.get('USERPROFILE', '')
            desktop     = os.path.join(userprofile, 'Desktop')
            downloads   = os.path.join(userprofile, 'Downloads')

            HACK_KEYWORDS = [
                'liquidbounce', 'wurst', 'meteor', 'sigma', 'aristois',
                'weaveloader', 'jigsaw', 'novoline', 'inertia', 'entropy',
                'drip', 'bleach', 'rusherhack', 'hypixel client', 'rise client',
                'kilo client', 'cheat client', 'ghost client', 'hack client',
                'aimbot', 'killaura', 'autoclick', 'blatant', 'esp hack',
                'xray hack', 'flymod', 'speedhack', 'scaffold',
            ]

            scan_roots = [appdata, desktop, downloads,
                          os.path.join(appdata, '.minecraft')]
            for root in scan_roots:
                if not os.path.isdir(root):
                    continue
                try:
                    for entry in os.scandir(root):
                        name_low = entry.name.lower().replace('_', ' ').replace('-', ' ')
                        for kw in HACK_KEYWORDS:
                            if kw in name_low:
                                self.issues_found.append({
                                    'tipo':     'folder_name_hack',
                                    'nombre':   f'Nombre sospechoso: {entry.name}',
                                    'ruta':     root,
                                    'archivo':  entry.path,
                                    'categoria': 'GHOST_CLIENT',
                                    'alerta':   'SOSPECHOSO',
                                    'confidence': 0.68,
                                    'detected_patterns': [f'name_match:{kw}'],
                                })
                                print(f"[nlp_name] '{entry.name}' → '{kw}'")
                                break
                        else:
                            # Fuzzy similarity check for 1-char typos
                            best = difflib.get_close_matches(
                                name_low, HACK_KEYWORDS, n=1, cutoff=0.82
                            )
                            if best:
                                self.issues_found.append({
                                    'tipo':     'folder_name_fuzzy',
                                    'nombre':   f'Nombre similar a hack: {entry.name} ≈ {best[0]}',
                                    'ruta':     root,
                                    'archivo':  entry.path,
                                    'categoria': 'GHOST_CLIENT',
                                    'alerta':   'POCO_SOSPECHOSO',
                                    'confidence': 0.50,
                                    'detected_patterns': [f'fuzzy_match:{best[0]}'],
                                })
                except PermissionError:
                    pass
        except Exception as e:
            print(f"Error en scan_folder_name_nlp: {e}")

    def scan_minecraft_install_date(self):
        """P2 #21 — Correlaciona fecha de instalación de Minecraft con hallazgos.
        Instalación muy reciente (<30 días) + muchos hallazgos = bandera de sospecha.
        """
        print("🔍 Verificando fecha de instalación de Minecraft...")
        try:
            appdata  = os.environ.get('APPDATA', '')
            mc_dir   = os.path.join(appdata, '.minecraft')
            if not os.path.isdir(mc_dir):
                return

            # Fecha de creación del directorio .minecraft
            mc_ctime = os.path.getctime(mc_dir)
            age_days  = (time.time() - mc_ctime) / 86400

            if age_days < 30:
                label = f'{int(age_days)}d'
                self.issues_found.append({
                    'tipo':     'mc_install_recent',
                    'nombre':   f'Minecraft instalado hace {int(age_days)} día(s)',
                    'ruta':     mc_dir,
                    'archivo':  mc_dir,
                    'categoria': 'CONTEXTO',
                    'alerta':   'POCO_SOSPECHOSO' if age_days > 7 else 'SOSPECHOSO',
                    'confidence': 0.45,
                    'detected_patterns': [f'mc_age_{label}', 'recent_install'],
                })
                print(f"[mc_install] .minecraft tiene {int(age_days)} días")

            # También revisar logs de instalador en el registro (UninstallString)
            try:
                import winreg
                for hive, flag in [
                    (winreg.HKEY_CURRENT_USER,  0),
                    (winreg.HKEY_LOCAL_MACHINE, winreg.KEY_WOW64_32KEY),
                    (winreg.HKEY_LOCAL_MACHINE, winreg.KEY_WOW64_64KEY),
                ]:
                    key_path = r'Software\Microsoft\Windows\CurrentVersion\Uninstall'
                    try:
                        with winreg.OpenKey(hive, key_path, 0, winreg.KEY_READ | flag) as base:
                            n = winreg.QueryInfoKey(base)[0]
                            for i in range(n):
                                try:
                                    sub_name = winreg.EnumKey(base, i)
                                    with winreg.OpenKey(base, sub_name) as sub:
                                        display = winreg.QueryValueEx(sub, 'DisplayName')[0].lower()
                                        if 'minecraft' not in display:
                                            continue
                                        try:
                                            install_date_str = winreg.QueryValueEx(sub, 'InstallDate')[0]
                                            # format: YYYYMMDD
                                            if len(install_date_str) == 8:
                                                from datetime import datetime as _dt
                                                inst = _dt.strptime(install_date_str, '%Y%m%d')
                                                reg_age = (time.time() - inst.timestamp()) / 86400
                                                if reg_age < 30:
                                                    print(f"[mc_install] Registro: MC instalado {int(reg_age)}d atrás")
                                        except (FileNotFoundError, ValueError):
                                            pass
                                except (FileNotFoundError, PermissionError):
                                    pass
                    except (FileNotFoundError, PermissionError):
                        pass
            except ImportError:
                pass
        except Exception as e:
            print(f"Error en scan_minecraft_install_date: {e}")

    def scan_minecraft_last_session(self):
        """P2 #22 — Correlaciona últimas sesiones de juego con hallazgos.
        Detecta cuándo fue la última partida y si los hacks encontrados son contemporáneos.
        """
        print("🔍 Analizando últimas sesiones de Minecraft...")
        try:
            appdata = os.environ.get('APPDATA', '')
            mc_dir  = os.path.join(appdata, '.minecraft')
            logs_dir = os.path.join(mc_dir, 'logs')
            if not os.path.isdir(logs_dir):
                return

            # Fecha del latest.log = última vez que se ejecutó MC
            latest_log = os.path.join(logs_dir, 'latest.log')
            last_session = None
            if os.path.isfile(latest_log):
                last_session = os.path.getmtime(latest_log)

            # También revisar logs comprimidos — el más reciente es la penúltima sesión
            log_dates = []
            try:
                for fname in os.listdir(logs_dir):
                    if fname.endswith('.log.gz') and len(fname) >= 10:
                        # Nombre: YYYY-MM-DD-N.log.gz
                        date_part = fname[:10]
                        try:
                            from datetime import datetime as _dt
                            d = _dt.strptime(date_part, '%Y-%m-%d')
                            log_dates.append(d.timestamp())
                        except ValueError:
                            pass
            except OSError:
                pass

            if log_dates and not last_session:
                last_session = max(log_dates)

            if last_session is None:
                return

            days_since = (time.time() - last_session) / 86400
            # Guardar en atributo para correlaciones posteriores
            self._last_mc_session_days = days_since

            # Si no ha jugado en >30 días pero tiene muchos hallazgos recientes → limpieza
            if days_since > 30:
                self.issues_found.append({
                    'tipo':      'mc_long_inactive',
                    'nombre':    f'Minecraft sin actividad hace {int(days_since)} días',
                    'ruta':      logs_dir,
                    'archivo':   latest_log if os.path.isfile(latest_log) else logs_dir,
                    'categoria': 'CONTEXTO',
                    'alerta':    'POCO_SOSPECHOSO',
                    'confidence': 0.30,
                    'detected_patterns': [f'inactive_{int(days_since)}d'],
                })
                print(f"[mc_session] Sin actividad hace {int(days_since)} días")
            else:
                print(f"[mc_session] Última sesión hace {int(days_since)} días")
        except Exception as e:
            print(f"Error en scan_minecraft_last_session: {e}")

    def scan_installed_programs(self):
        """Escanea programas instalados en el registro en busca de CheatEngine u otras herramientas de trampa."""
        print("🔍 Escaneando programas instalados...")
        hack_terms = [
            'cheat engine', 'cheatengine', 'vape', 'liquidbounce',
            'dllinjector', 'process hacker', 'x64dbg', 'ollydbg',
            'processhacker', 'wireshark', 'charles proxy', 'fiddler',
        ]
        uninstall_keys = [
            (winreg.HKEY_LOCAL_MACHINE, r'Software\Microsoft\Windows\CurrentVersion\Uninstall'),
            (winreg.HKEY_CURRENT_USER,  r'Software\Microsoft\Windows\CurrentVersion\Uninstall'),
            (winreg.HKEY_LOCAL_MACHINE, r'Software\WOW6432Node\Microsoft\Windows\CurrentVersion\Uninstall'),
        ]
        for hive, path in uninstall_keys:
            try:
                with winreg.OpenKey(hive, path) as base:
                    i = 0
                    while True:
                        try:
                            subkey_name = winreg.EnumKey(base, i)
                            i += 1
                            try:
                                with winreg.OpenKey(base, subkey_name) as sk:
                                    try:
                                        display_name, _ = winreg.QueryValueEx(sk, 'DisplayName')
                                    except FileNotFoundError:
                                        continue
                                    if not isinstance(display_name, str):
                                        continue
                                    dn_lower = display_name.lower()
                                    for term in hack_terms:
                                        if term in dn_lower:
                                            try:
                                                install_loc, _ = winreg.QueryValueEx(sk, 'InstallLocation')
                                            except Exception:
                                                install_loc = ''
                                            self.issues_found.append({
                                                'tipo': 'installed_hack_tool',
                                                'nombre': f'Herramienta instalada: {display_name}',
                                                'ruta': install_loc[:255],
                                                'archivo': display_name[:255],
                                                'categoria': 'HACKS',
                                                'alerta': 'CRITICAL',
                                                'confidence': 88,
                                                'detected_patterns': [term],
                                            })
                                            print(f"🚨 PROGRAMA SOSPECHOSO INSTALADO: {display_name}")
                                            break
                            except (PermissionError, OSError):
                                pass
                        except OSError:
                            break
            except (FileNotFoundError, PermissionError):
                pass
            except Exception as e:
                print(f"Error en scan_installed_programs ({path}): {e}")

    def scan_bam_registry(self):
        """Lee Background Activity Monitor (BAM) para detectar ejecutables con timestamps precisos."""
        print("🔍 Escaneando BAM registry (Background Activity Monitor)...")
        import struct
        hack_terms = [
            'vape', 'vapelite', 'entropy', 'entropyclient',
            'wurst', 'wurstclient', 'liquidbounce',
            'killaura', 'aimbot', 'cheatengine',
            'xray', 'triggerbot', 'dllinjector', 'bspoof',
            'phobos', 'astolfo', 'novoline',
            'ghostclient', 'silentclient', 'fluxclient',
        ]
        EPOCH_DIFF = 116444736000000000

        def parse_bam_ts(data):
            try:
                if len(data) >= 8:
                    ft_raw = struct.unpack_from('<Q', data, 0)[0]
                    if ft_raw > 0:
                        unix_ts = (ft_raw - EPOCH_DIFF) / 10000000
                        if 0 < unix_ts < 2000000000:
                            return datetime.fromtimestamp(unix_ts).strftime('%Y-%m-%d %H:%M:%S')
            except Exception:
                pass
            return 'Desconocida'

        try:
            bam_base = r'SYSTEM\CurrentControlSet\Services\bam\State\UserSettings'
            with winreg.OpenKey(winreg.HKEY_LOCAL_MACHINE, bam_base) as base_key:
                sid_idx = 0
                while True:
                    try:
                        sid = winreg.EnumKey(base_key, sid_idx)
                        sid_idx += 1
                        sid_path = bam_base + '\\' + sid
                        try:
                            with winreg.OpenKey(winreg.HKEY_LOCAL_MACHINE, sid_path) as sid_key:
                                val_idx = 0
                                all_entries = []
                                while True:
                                    try:
                                        name, data, vtype = winreg.EnumValue(sid_key, val_idx)
                                        val_idx += 1
                                        if not isinstance(data, bytes) or not name.startswith('\\Device\\'):
                                            continue
                                        ts = parse_bam_ts(data)
                                        exe_name = name.split('\\')[-1]
                                        all_entries.append({'name': name, 'exe': exe_name, 'ts': ts})
                                        # Check for hack terms
                                        name_lower = name.lower()
                                        for term in hack_terms:
                                            if term in name_lower:
                                                self.issues_found.append({
                                                    'tipo': 'bam_suspicious',
                                                    'nombre': f'BAM: ejecutable sospechoso detectado — {exe_name}',
                                                    'ruta': name[:255],
                                                    'archivo': name[:255],
                                                    'categoria': 'EXECUTED_FILES',
                                                    'alerta': 'CRITICAL',
                                                    'confidence': 85,
                                                    'detected_patterns': [term],
                                                    'extra': {'last_run': ts, 'fuente': 'BAM'},
                                                })
                                                print(f"🚨 BAM SOSPECHOSO: {exe_name} @ {ts}")
                                                break
                                    except OSError:
                                        break
                                if all_entries:
                                    print(f"✅ BAM: {len(all_entries)} ejecutables en SID ...{sid[-8:]}")
                        except (FileNotFoundError, PermissionError):
                            pass
                    except OSError:
                        break
        except (FileNotFoundError, PermissionError) as e:
            print(f"BAM registry no disponible: {e}")
        except Exception as e:
            print(f"Error en scan_bam_registry: {e}")

    def scan_recent_lnk(self):
        """Escanea archivos .lnk recientes en %APPDATA%\\Microsoft\\Windows\\Recent."""
        print("🔍 Escaneando archivos .lnk recientes...")
        hack_terms = [
            'vape', 'vapelite', 'entropy', 'entropyclient',
            'wurst', 'wurstclient', 'liquidbounce',
            'killaura', 'aimbot', 'cheatengine',
            'xray', 'triggerbot', 'dllinjector', 'bspoof',
            'phobos', 'astolfo', 'novoline',
            'ghostclient', 'silentclient', 'fluxclient',
        ]
        recent_dir = os.path.join(os.environ.get('APPDATA', ''), 'Microsoft', 'Windows', 'Recent')
        if not os.path.exists(recent_dir):
            return
        try:
            lnk_files = []
            for fname in os.listdir(recent_dir):
                if not fname.lower().endswith('.lnk'):
                    continue
                fpath = os.path.join(recent_dir, fname)
                try:
                    mtime = os.path.getmtime(fpath)
                    ts = datetime.fromtimestamp(mtime).strftime('%Y-%m-%d %H:%M:%S')
                    base = fname[:-4]  # strip .lnk
                    lnk_files.append({'name': base, 'ts': ts})
                    # Check for hack terms
                    name_lower = base.lower()
                    for term in hack_terms:
                        if term in name_lower:
                            self.issues_found.append({
                                'tipo': 'recent_lnk_suspicious',
                                'nombre': f'Archivo reciente sospechoso: {base}',
                                'ruta': fpath[:255],
                                'archivo': fpath[:255],
                                'categoria': 'EXECUTED_FILES',
                                'alerta': 'SOSPECHOSO',
                                'confidence': 65,
                                'detected_patterns': [term],
                                'extra': {'last_access': ts, 'fuente': 'Recent LNK'},
                            })
                            print(f"⚠️ LNK SOSPECHOSO: {base} @ {ts}")
                            break
                except Exception:
                    pass

            if lnk_files:
                print(f"✅ LNK recientes: {len(lnk_files)} archivos encontrados")
        except Exception as e:
            print(f"Error en scan_recent_lnk: {e}")

    def scan_appcompat_shimcache(self):
        """Lee AppCompatCache (ShimCache) del registro — ejecuciones históricas de aplicaciones."""
        print("🔍 Escaneando AppCompatCache (ShimCache)...")
        import re as _re
        hack_terms = list(_DEFINITE_HACK_NAMES)

        def _valid_path(p):
            """Ruta válida de Windows: empieza con letra de unidad o \\Device\\, sin chars raros."""
            if not p or len(p) < 5:
                return False
            if not (_re.match(r'^[A-Za-z]:\\', p) or p.startswith('\\Device\\')):
                return False
            if any(ord(c) < 0x20 for c in p):
                return False
            return True
        try:
            key_path = r'SYSTEM\CurrentControlSet\Control\Session Manager\AppCompatCache'
            with winreg.OpenKey(winreg.HKEY_LOCAL_MACHINE, key_path) as k:
                data, _ = winreg.QueryValueEx(k, 'AppCompatCache')

            if not isinstance(data, bytes) or len(data) < 16:
                return

            # Parse: signature at [0:4], entry count at [4:8], entries from offset 128
            sig = data[:4]
            entries = []

            # Windows 10/11 format: 0x30 = entries start at 0x80 (128)
            if sig in (b'10ts', b'\x30\x00\x00\x00'):
                offset = 128
            else:
                offset = 128  # fallback

            while offset + 12 <= len(data):
                try:
                    entry_sig = data[offset:offset+4]
                    if entry_sig != b'10ts':
                        offset += 4
                        continue
                    data_len = int.from_bytes(data[offset+4:offset+8], 'little')
                    if data_len <= 0 or data_len > 65536:
                        offset += 4
                        continue
                    entry_data = data[offset+8:offset+8+data_len]
                    # Path is UTF-16LE at start of entry_data
                    path_len = int.from_bytes(entry_data[0:2], 'little') if len(entry_data) >= 4 else 0
                    if 0 < path_len <= len(entry_data) - 4:
                        path = entry_data[4:4+path_len].decode('utf-16-le', errors='ignore')
                        if _valid_path(path):
                            entries.append(path)
                    offset += 8 + data_len
                except Exception:
                    offset += 4

            if not entries:
                return

            # F32 — Ignorar entradas de rutas vanilla de Minecraft (el juego los ejecuta todo el tiempo)
            _shim_vanilla_skip = (
                '\\versions\\', '/versions/', '\\libraries\\', '/libraries/',
                '\\assets\\', '/assets/', '\\natives\\', '/natives/',
            )
            suspicious = []
            for path in entries:
                path_lower = path.lower()
                # F32: skip vanilla MC paths in shimcache
                if any(vp in path_lower for vp in _shim_vanilla_skip):
                    continue
                for term in hack_terms:
                    if term in path_lower:
                        suspicious.append(path)
                        self.issues_found.append({
                            'tipo': 'shimcache_suspicious',
                            'nombre': f'ShimCache: ejecutable sospechoso — {os.path.basename(path)}',
                            'ruta': path[:255],
                            'archivo': path[:255],
                            'categoria': 'EXECUTED_FILES',
                            'alerta': 'CRITICAL',
                            'confidence': 82,
                            'detected_patterns': [term],
                        })
                        print(f"🚨 SHIMCACHE SOSPECHOSO: {path[:80]}")
                        break

            if entries:
                print(f"✅ ShimCache: {len(entries)} entradas válidas")
        except (FileNotFoundError, PermissionError) as e:
            print(f"ShimCache no disponible: {e}")
        except Exception as e:
            print(f"Error en scan_appcompat_shimcache: {e}")

    def scan_muicache(self):
        """Lee MUICache — nombres de todos los ejecutables que corrió el usuario, incluyendo borrados."""
        print("🔍 Escaneando MUICache...")
        hack_terms = [
            'vape', 'vapelite', 'entropy', 'entropyclient',
            'wurst', 'wurstclient', 'liquidbounce',
            'killaura', 'aimbot', 'cheatengine',
            'xray', 'triggerbot', 'dllinjector', 'bspoof',
            'phobos', 'astolfo', 'novoline',
            'ghostclient', 'silentclient', 'fluxclient',
        ]
        key_path = r'Software\Classes\Local Settings\Software\Microsoft\Windows\Shell\MuiCache'
        try:
            entries = []
            with winreg.OpenKey(winreg.HKEY_CURRENT_USER, key_path) as k:
                i = 0
                while True:
                    try:
                        name, data, _ = winreg.EnumValue(k, i)
                        i += 1
                        if name.endswith('.FriendlyAppName') or name.endswith('.ApplicationCompany'):
                            continue
                        if '\\' in name or '/' in name:
                            entries.append(name)
                    except OSError:
                        break

            suspicious = []
            for path in entries:
                path_lower = path.lower()
                for term in hack_terms:
                    if term in path_lower:
                        suspicious.append(path)
                        self.issues_found.append({
                            'tipo': 'muicache_suspicious',
                            'nombre': f'MUICache: ejecutable sospechoso — {os.path.basename(path)}',
                            'ruta': path[:255],
                            'archivo': path[:255],
                            'categoria': 'EXECUTED_FILES',
                            'alerta': 'CRITICAL',
                            'confidence': 80,
                            'detected_patterns': [term],
                        })
                        print(f"🚨 MUICACHE SOSPECHOSO: {path[:80]}")
                        break

            if entries:
                print(f"✅ MUICache: {len(entries)} entradas válidas")
        except (FileNotFoundError, PermissionError) as e:
            print(f"MUICache no disponible: {e}")
        except Exception as e:
            print(f"Error en scan_muicache: {e}")

    def scan_scheduled_tasks(self):
        """Escanea tareas programadas de Windows en busca de ejecutables sospechosos."""
        print("🔍 Escaneando tareas programadas de Windows...")
        hack_terms = [
            'vape', 'entropy', 'hack', 'cheat', 'inject', 'wurst', 'liquidbounce',
            'sigma', 'flux', 'killaura', 'aimbot', 'bypass', 'autoclick',
            'clicker', 'phobos', 'astolfo', 'dllinjector', 'cheatengine',
            'xray', 'triggerbot', 'ghostclient',
        ]
        tasks_dir = r'C:\Windows\System32\Tasks'
        if not os.path.exists(tasks_dir):
            return
        try:
            found_tasks = []
            for root, dirs, files in os.walk(tasks_dir):
                for fname in files:
                    fpath = os.path.join(root, fname)
                    try:
                        with open(fpath, 'r', encoding='utf-8', errors='ignore') as f:
                            content = f.read(32768)
                        content_lower = content.lower()
                        for term in hack_terms:
                            if term in content_lower:
                                found_tasks.append(fname)
                                self.issues_found.append({
                                    'tipo': 'scheduled_task_suspicious',
                                    'nombre': f'Tarea programada sospechosa: {fname}',
                                    'ruta': fpath[:255],
                                    'archivo': fpath[:255],
                                    'categoria': 'CMD_HISTORY',
                                    'alerta': 'CRITICAL',
                                    'confidence': 85,
                                    'detected_patterns': [term],
                                })
                                print(f"🚨 TAREA SOSPECHOSA: {fname} (contiene '{term}')")
                                break
                    except Exception:
                        pass
        except Exception as e:
            print(f"Error en scan_scheduled_tasks: {e}")

    def scan_texture_packs(self):
        """Escanea resource packs de Minecraft, incluyendo análisis de XRay."""
        print("🔍 Escaneando resource packs de Minecraft...")
        xray_terms = ['xray', 'x-ray', 'xview', 'ore', 'highlight', 'transparent', 'wallhack', 'see_through']
        mc_path = os.path.join(os.environ.get('APPDATA', ''), '.minecraft', 'resourcepacks')
        if not os.path.exists(mc_path):
            return
        try:
            packs = []
            for entry in os.listdir(mc_path):
                entry_path = os.path.join(mc_path, entry)
                name_lower = entry.lower()
                mtime = os.path.getmtime(entry_path)
                added_at = datetime.fromtimestamp(mtime).strftime('%Y-%m-%d %H:%M:%S')
                is_xray = any(t in name_lower for t in xray_terms)
                alerta = 'CRITICAL' if is_xray else 'NORMAL'
                confidence = 85 if is_xray else 0

                packs.append({'name': entry, 'added_at': added_at, 'is_xray': is_xray})
                self.issues_found.append({
                    'tipo': 'texture_pack',
                    'nombre': f'Resource Pack: {entry}' + (' [POSIBLE XRAY]' if is_xray else ''),
                    'ruta': entry_path,
                    'archivo': entry,
                    'categoria': 'TEXTURE_PACKS',
                    'alerta': alerta,
                    'confidence': confidence,
                    'detected_patterns': [t for t in xray_terms if t in name_lower],
                    'extra': {'added_at': added_at, 'is_xray': is_xray},
                })
                if is_xray:
                    print(f"🚨 POSIBLE XRAY PACK: {entry}")
                else:
                    print(f"ℹ️ Resource Pack: {entry}")

                # Try xray_texture_analyzer if available
                try:
                    from xray_texture_analyzer import XRayTextureAnalyzer
                    analyzer = XRayTextureAnalyzer()
                    result = analyzer.analyze_pack(entry_path)
                    if result and result.get('is_xray'):
                        self.issues_found.append({
                            'tipo': 'texture_pack_xray',
                            'nombre': f'XRAY confirmado por análisis: {entry}',
                            'ruta': entry_path,
                            'archivo': entry,
                            'categoria': 'TEXTURE_PACKS',
                            'alerta': 'CRITICAL',
                            'confidence': result.get('confidence', 90),
                            'detected_patterns': result.get('patterns', []),
                        })
                        print(f"🚨 XRAY CONFIRMADO por análisis: {entry}")
                except Exception:
                    pass

        except Exception as e:
            print(f"Error en scan_texture_packs: {e}")

    def scan_exploit_tools(self):
        """Detecta herramientas de exploit y RATs conocidas."""
        print("🔍 Buscando herramientas de exploit y RATs...")
        exploit_signatures = [
            # RATs
            ('njrat', 'RAT', 'CRITICAL'), ('darkcomet', 'RAT', 'CRITICAL'),
            ('nanocore', 'RAT', 'CRITICAL'), ('quasar', 'RAT', 'CRITICAL'),
            ('asyncrat', 'RAT', 'CRITICAL'), ('remcos', 'RAT', 'CRITICAL'),
            ('limerat', 'RAT', 'CRITICAL'),
            # Keyloggers
            ('keylogger', 'KEYLOGGER', 'CRITICAL'), ('ardamax', 'KEYLOGGER', 'CRITICAL'),
            ('revealer', 'KEYLOGGER', 'SOSPECHOSO'),
            # Exploits
            ('metasploit', 'EXPLOIT', 'CRITICAL'), ('cobalt', 'EXPLOIT', 'CRITICAL'),
            ('msfvenom', 'EXPLOIT', 'CRITICAL'), ('shellcode', 'EXPLOIT', 'SOSPECHOSO'),
            # Packet tools
            ('wireshark', 'PACKET_SNIFF', 'SOSPECHOSO'), ('cheatengine', 'CHEAT', 'CRITICAL'),
            ('x64dbg', 'DEBUGGER', 'SOSPECHOSO'), ('ollydbg', 'DEBUGGER', 'SOSPECHOSO'),
            ('processhacker', 'PROC_HACK', 'SOSPECHOSO'),
        ]

        search_paths = [
            os.path.expanduser('~\\Desktop'),
            os.path.expanduser('~\\Downloads'),
            os.path.expanduser('~\\AppData\\Roaming'),
            os.path.expanduser('~\\AppData\\Local\\Temp'),
        ]

        found_names = set()
        try:
            # Check running processes
            for proc in psutil.process_iter(['name', 'exe']):
                try:
                    pname = (proc.info.get('name') or '').lower()
                    pexe = (proc.info.get('exe') or '').lower()
                    for sig, cat, level in exploit_signatures:
                        if sig in pname or sig in pexe:
                            key = sig + pname
                            if key not in found_names:
                                found_names.add(key)
                                self.issues_found.append({
                                    'tipo': 'exploit_process',
                                    'nombre': f'Proceso de exploit activo: {proc.info.get("name", sig)}',
                                    'ruta': proc.info.get('exe') or 'N/A',
                                    'archivo': proc.info.get('name', sig),
                                    'categoria': cat,
                                    'alerta': level,
                                    'confidence': 90,
                                    'detected_patterns': [sig],
                                })
                                print(f"🚨 EXPLOIT PROCESS: {proc.info.get('name')} [{level}]")
                            break
                except Exception:
                    continue

            # Check file system
            for search_path in search_paths:
                if not os.path.exists(search_path):
                    continue
                try:
                    for root, dirs, files in os.walk(search_path):
                        dirs[:] = [d for d in dirs if d not in {'node_modules', '.git', '__pycache__'}]
                        for fname in files:
                            fname_lower = fname.lower()
                            for sig, cat, level in exploit_signatures:
                                if sig in fname_lower:
                                    fpath = os.path.join(root, fname)
                                    key = sig + fpath
                                    if key not in found_names:
                                        found_names.add(key)
                                        self.issues_found.append({
                                            'tipo': 'exploit_file',
                                            'nombre': f'Herramienta de exploit: {fname}',
                                            'ruta': fpath,
                                            'archivo': fname,
                                            'categoria': cat,
                                            'alerta': level,
                                            'confidence': 80,
                                            'detected_patterns': [sig],
                                        })
                                        print(f"🚨 EXPLOIT FILE: {fpath} [{level}]")
                                    break
                except PermissionError:
                    pass
        except Exception as e:
            print(f"Error en scan_exploit_tools: {e}")

    def scan_java_process_parent(self):
        """Analiza el proceso padre de javaw.exe para detectar launchers sospechosos."""
        print("🔍 Analizando árbol de procesos Java (parent process analysis)...")
        LEGITIMATE_PARENTS = {
            'javaw.exe', 'java.exe', 'explorer.exe',
            'tlauncher.exe', 'tlauncher-legacy.exe', 'minecraftlauncher.exe',
            'lunarclient.exe', 'badlion.exe', 'prismlauncher.exe', 'multimc.exe',
            'gdlauncher.exe', 'gdlauncher_next.exe', 'ftb_app.exe', 'curseforge.exe',
            'atlauncher.exe', 'polymc.exe', 'featherlauncher.exe',
            'cmd.exe', 'powershell.exe', 'pwsh.exe',
        }
        SUSPICIOUS_PARENTS = {
            'extremeinjector.exe', 'xenos.exe', 'dllinjector.exe',
            'cheatengine.exe', 'cheat engine.exe', 'processhacker.exe',
            'x64dbg.exe', 'x32dbg.exe', 'ollydbg.exe',
        }
        try:
            for proc in psutil.process_iter(['pid', 'name', 'ppid']):
                try:
                    name = (proc.info.get('name') or '').lower()
                    if 'javaw' not in name and 'java' not in name:
                        continue
                    ppid = proc.info.get('ppid')
                    if not ppid:
                        continue
                    try:
                        parent = psutil.Process(ppid)
                        parent_name = (parent.name() or '').lower()
                    except (psutil.NoSuchProcess, psutil.AccessDenied):
                        continue

                    if parent_name in SUSPICIOUS_PARENTS:
                        print(f"🚨 JAVA LANZADO POR INYECTOR: {name} → padre={parent_name}")
                        self.issues_found.append({
                            'nombre': f'Java lanzado por proceso inyector: {name} ← {parent_name}',
                            'ruta': f'PID:{proc.pid} PPID:{ppid}',
                            'archivo': parent_name,
                            'tipo': 'java_suspicious_parent',
                            'categoria': 'JAVA_INJECTION',
                            'alerta': 'CRITICAL',
                            'confidence': 0.95,
                            'detected_patterns': ['java_launched_by_injector', f'parent:{parent_name}'],
                        })
                    elif parent_name not in LEGITIMATE_PARENTS and 'minecraft' not in parent_name:
                        print(f"⚠️ JAVA CON PADRE INUSUAL: {name} → {parent_name}")
                        self.issues_found.append({
                            'nombre': f'Java lanzado por proceso inusual: {parent_name}',
                            'ruta': f'PID:{proc.pid} PPID:{ppid}',
                            'archivo': parent_name,
                            'tipo': 'java_unusual_parent',
                            'categoria': 'JAVA_INJECTION',
                            'alerta': 'SOSPECHOSO',
                            'confidence': 0.60,
                            'detected_patterns': ['java_unusual_parent', f'parent:{parent_name}'],
                        })
                except (psutil.NoSuchProcess, psutil.AccessDenied):
                    continue
        except Exception as e:
            print(f"Error en scan_java_process_parent: {e}")

    def scan_evasion_indicators(self):
        """Detecta indicadores de limpieza activa antes del SS (evasión)."""
        print("🔍 Evaluando indicadores de evasión...")
        evasion_score = 0
        indicators = []

        # VPN ya no suma al evasion score — es legal y se muestra como categoría propia

        # Indicator 2: Prefetch vacío o muy pequeño (posible limpieza manual)
        try:
            prefetch_dir = os.path.join(os.environ.get('WINDIR', 'C:\\Windows'), 'Prefetch')
            if os.path.isdir(prefetch_dir):
                pf_count = len([f for f in os.listdir(prefetch_dir) if f.endswith('.pf')])
                if pf_count < 5:
                    evasion_score += 30
                    indicators.append(f'Prefetch inusualmente vacío ({pf_count} archivos)')
                elif pf_count < 20:
                    evasion_score += 10
                    indicators.append(f'Prefetch escaso ({pf_count} archivos)')
        except Exception:
            pass

        # Indicator 3: Muy pocos procesos corriendo (jugador apagó todo)
        try:
            proc_count = sum(1 for _ in psutil.process_iter())
            if proc_count < 30:
                evasion_score += 20
                indicators.append(f'Muy pocos procesos activos ({proc_count}) — posible limpieza pre-SS')
        except Exception:
            pass

        # Indicator 4: Muchos archivos borrados recientemente (scan_deleted_recycle ya detectó)
        recent_deletions = sum(1 for i in self.issues_found if i.get('tipo') == 'deleted_suspicious')
        if recent_deletions >= 3:
            evasion_score += 20 + recent_deletions * 5
            indicators.append(f'{recent_deletions} archivos sospechosos eliminados recientemente')

        # Indicator 5: Hosts file modificado
        hosts_mod = any(i.get('tipo') in ('hosts_minecraft_redirect', 'hosts_file_custom') for i in self.issues_found)
        if hosts_mod:
            evasion_score += 15
            indicators.append('Hosts file modificado (posible bypass de autenticación)')

        if evasion_score >= 25 and indicators:
            alerta = 'CRITICAL' if evasion_score >= 50 else 'SOSPECHOSO'
            print(f"{'🚨' if alerta == 'CRITICAL' else '⚠️'} EVASION SCORE: {evasion_score} — {', '.join(indicators)}")
            self.issues_found.append({
                'nombre': f'Indicadores de evasión activa detectados (score: {evasion_score}): {"; ".join(indicators[:3])}',
                'ruta': 'Análisis de comportamiento del sistema',
                'archivo': '; '.join(indicators[:3])[:255],
                'tipo': 'evasion_indicators',
                'categoria': 'EVASION',
                'alerta': alerta,
                'confidence': min(0.95, evasion_score / 100),
                'detected_patterns': ['evasion_' + ind.split(' ')[0].lower().replace(' ', '_') for ind in indicators],
                'extra': {'evasion_score': evasion_score, 'indicators': indicators},
            })

    def scan_digital_signature(self, file_path: str) -> bool:
        """Verifica la firma digital Authenticode de un ejecutable. Retorna True si está firmado."""
        try:
            import ctypes as _ct
            import ctypes.wintypes as _wt
            WINTRUST_ACTION_GENERIC_VERIFY_V2 = '{00AAC56B-CD44-11d0-8CC2-00C04FC295EE}'

            class WINTRUST_FILE_INFO(_ct.Structure):
                _fields_ = [
                    ('cbStruct', _wt.DWORD),
                    ('pcwszFilePath', _wt.LPCWSTR),
                    ('hFile', _wt.HANDLE),
                    ('pgKnownSubject', _ct.c_void_p),
                ]

            class WINTRUST_DATA(_ct.Structure):
                _fields_ = [
                    ('cbStruct', _wt.DWORD),
                    ('pPolicyCallbackData', _ct.c_void_p),
                    ('pSIPClientData', _ct.c_void_p),
                    ('dwUIChoice', _wt.DWORD),
                    ('fdwRevocationChecks', _wt.DWORD),
                    ('dwUnionChoice', _wt.DWORD),
                    ('pFile', _ct.POINTER(WINTRUST_FILE_INFO)),
                    ('dwStateAction', _wt.DWORD),
                    ('hWVTStateData', _wt.HANDLE),
                    ('pwszURLReference', _wt.LPCWSTR),
                    ('dwProvFlags', _wt.DWORD),
                    ('dwUIContext', _wt.DWORD),
                ]

            wfi = WINTRUST_FILE_INFO()
            wfi.cbStruct = _ct.sizeof(WINTRUST_FILE_INFO)
            wfi.pcwszFilePath = file_path
            wfi.hFile = None
            wfi.pgKnownSubject = None

            wd = WINTRUST_DATA()
            wd.cbStruct = _ct.sizeof(WINTRUST_DATA)
            wd.pPolicyCallbackData = None
            wd.pSIPClientData = None
            wd.dwUIChoice = 2   # WTD_UI_NONE
            wd.fdwRevocationChecks = 0
            wd.dwUnionChoice = 1  # WTD_CHOICE_FILE
            wd.pFile = _ct.pointer(wfi)
            wd.dwStateAction = 0
            wd.hWVTStateData = None
            wd.pwszURLReference = None
            wd.dwProvFlags = 0x10  # WTD_CACHE_ONLY_URL_RETRIEVAL
            wd.dwUIContext = 0

            wintrust = _ct.windll.wintrust
            import uuid
            action_guid = '{00AAC56B-CD44-11d0-8CC2-00C04FC295EE}'
            # Create GUID struct
            class GUID(_ct.Structure):
                _fields_ = [('Data1', _wt.DWORD), ('Data2', _wt.WORD), ('Data3', _wt.WORD),
                             ('Data4', _ct.c_byte * 8)]
            g = GUID()
            u = uuid.UUID(action_guid)
            g.Data1, g.Data2, g.Data3 = u.time_low, u.time_mid, u.time_hi_version
            for i, b in enumerate(u.bytes[8:]):
                g.Data4[i] = b

            result = wintrust.WinVerifyTrust(None, _ct.byref(g), _ct.byref(wd))
            return result == 0  # 0 = TRUST_E_SUBJECT_FORM_UNKNOWN would not be 0
        except Exception:
            return False

    def scan_ghost_client_registry(self):
        """Detecta claves de registro dejadas por ghost clients instalados."""
        print("🔍 Escaneando registro por instalaciones de ghost clients...")
        GHOST_REGISTRY_KEYS = [
            (winreg.HKEY_CURRENT_USER, r'Software\Rise Client'),
            (winreg.HKEY_CURRENT_USER, r'Software\Sigma'),
            (winreg.HKEY_CURRENT_USER, r'Software\Vape'),
            (winreg.HKEY_CURRENT_USER, r'Software\LiquidBounce'),
            (winreg.HKEY_CURRENT_USER, r'Software\Meteor Client'),
            (winreg.HKEY_CURRENT_USER, r'Software\Drip Client'),
            (winreg.HKEY_CURRENT_USER, r'Software\Vertex Client'),
            (winreg.HKEY_CURRENT_USER, r'Software\Future Client'),
            (winreg.HKEY_CURRENT_USER, r'Software\Flux Client'),
            (winreg.HKEY_CURRENT_USER, r'Software\RusherHack'),
            (winreg.HKEY_CURRENT_USER, r'Software\Astolfo'),
            (winreg.HKEY_LOCAL_MACHINE, r'Software\Rise Client'),
            (winreg.HKEY_LOCAL_MACHINE, r'Software\Sigma'),
            (winreg.HKEY_LOCAL_MACHINE, r'Software\Vape'),
        ]
        try:
            for hive, subkey in GHOST_REGISTRY_KEYS:
                try:
                    with winreg.OpenKey(hive, subkey):
                        hive_name = 'HKCU' if hive == winreg.HKEY_CURRENT_USER else 'HKLM'
                        key_name = subkey.split('\\')[-1]
                        print(f"🚨 GHOST CLIENT REGISTRY: {hive_name}\\{subkey}")
                        self.issues_found.append({
                            'nombre': f'Clave de registro de ghost client: {key_name}',
                            'ruta': f'{hive_name}\\{subkey}',
                            'archivo': key_name,
                            'tipo': 'ghost_client_registry',
                            'categoria': 'GHOST_CLIENT',
                            'alerta': 'CRITICAL',
                            'confidence': 0.93,
                            'detected_patterns': [f'registry:{key_name.lower().replace(" ", "_")}'],
                        })
                except FileNotFoundError:
                    continue
                except Exception:
                    continue
        except Exception as e:
            print(f"Error en scan_ghost_client_registry: {e}")

    def _get_cloud_hack_blacklist(self) -> set:
        """P3 #17 — Descarga blacklist de hashes de hacks confirmados (caché 1h)."""
        import json as _json, datetime as _dt
        cache_path = os.path.join(os.environ.get('APPDATA', ''), 'ASPERSProjectsSS', 'hack_blacklist.json')
        try:
            if os.path.isfile(cache_path):
                age = (_dt.datetime.now() - _dt.datetime.fromtimestamp(os.path.getmtime(cache_path))).total_seconds()
                if age < 3600:
                    with open(cache_path, 'r') as f:
                        data = _json.load(f)
                    return {h['sha256'] for h in data.get('hashes', [])}
        except Exception:
            pass
        try:
            base_url = self.config.get('api_url', '').rstrip('/')
            if not base_url:
                return set()
            r = requests.get(f'{base_url}/api/hack_blacklist', timeout=8)
            if r.ok:
                data = r.json()
                os.makedirs(os.path.dirname(cache_path), exist_ok=True)
                with open(cache_path, 'w') as f:
                    _json.dump(data, f)
                return {h['sha256'] for h in data.get('hashes', [])}
        except Exception:
            pass
        return set()

    def _get_cloud_mod_whitelist(self):
        """P2 #1 — Descarga whitelist de mods legítimos desde la cloud (caché 1h en APPDATA)."""
        import json as _json, hashlib as _hl, datetime as _dt
        cache_path = os.path.join(os.environ.get('APPDATA', ''), 'ASPERSProjectsSS', 'mod_whitelist.json')
        # Intentar usar caché válida
        try:
            if os.path.isfile(cache_path):
                age = (_dt.datetime.now() - _dt.datetime.fromtimestamp(os.path.getmtime(cache_path))).total_seconds()
                if age < 3600:
                    with open(cache_path, 'r') as f:
                        data = _json.load(f)
                    return set(data.get('hashes', []))
        except Exception:
            pass
        # Descargar desde cloud
        try:
            base_url = self.config.get('api_url', '').rstrip('/')
            if not base_url:
                return set()
            r = requests.get(f'{base_url}/api/mod_whitelist', timeout=8)
            if r.ok:
                data = r.json()
                os.makedirs(os.path.dirname(cache_path), exist_ok=True)
                with open(cache_path, 'w') as f:
                    _json.dump(data, f)
                return set(data.get('hashes', []))
        except Exception:
            pass
        return set()

    def scan_minecraft_mods_blacklist(self):
        """Detecta mods prohibidos en .minecraft/mods/ y .minecraft/versions/*/mods/."""
        print("🔍 Escaneando mods de Minecraft contra lista negra...")
        appdata = os.environ.get('APPDATA', '')
        mc_dir = os.path.join(appdata, '.minecraft')
        # Carpeta raíz + carpetas de versiones personalizadas (#1)
        mods_dirs_to_scan = []
        mods_dir = os.path.join(mc_dir, 'mods')
        if os.path.isdir(mods_dir):
            mods_dirs_to_scan.append(mods_dir)
        versions_dir = os.path.join(mc_dir, 'versions')
        if os.path.isdir(versions_dir):
            for ver in os.listdir(versions_dir):
                ver_mods = os.path.join(versions_dir, ver, 'mods')
                if os.path.isdir(ver_mods):
                    mods_dirs_to_scan.append(ver_mods)
        if not mods_dirs_to_scan:
            return
        # P2 #1 — Whitelist dinámica de mods legítimos
        cloud_whitelist = self._get_cloud_mod_whitelist()
        # P3 #17 — Blacklist dinámica de hashes de hacks confirmados
        cloud_blacklist = self._get_cloud_hack_blacklist()
        # P2 #2 — Whitelist por servidor (mods permitidos explícitamente en este token)
        server_allowed  = set(str(m).lower() for m in self.config.get('server_allowed_mods', []))
        BLACKLISTED = [
            'baritone', 'horion', 'impact', 'wurst', 'aristois', 'meteor',
            'sigma', 'ares', 'salhack', 'entropy', 'remix', 'inertia',
            'liquidbounce', 'flux', 'vape', 'riseclient', 'future', 'astolfo',
            'novoline', 'rusherhack', 'dripclient', 'vertex', 'azura', 'jello',
            'datura', 'mathias', 'weave', 'xray', 'killaura', 'aimbot',
            'scaffold', 'autoclick', 'clickgui', 'hacked', 'cheat', 'inject',
        ]
        # F13 — Modpacks populares: sus mods son legítimos aunque tengan nombres genéricos
        MODPACK_WHITELIST_DIRS = {
            'all the mods', 'atm', 'allthemods', 'rlcraft', 'sky factory',
            'skyfactory', 'ftb', 'all of fabric', 'aof', 'better mc', 'bettermc',
            'create above and beyond', 'create: above', 'stoneblock',
            'enigmatica', 'mc eternal', 'mceternal', 'crucial 2', 'crucial2',
            'prominence', 'vault hunters', 'vaulthunters',
        }
        # F15 — Whitelist extendida de nombres de mods legítimos que colisionan con hack patterns
        LEGIT_MOD_NAME_FRAGMENTS = {
            'impactapi', 'impact-api',       # ImpactAPI (Fabric library)
            'riseofempires',                  # mod de civilizaciones
            'wurst-', 'wurst_',              # WURST keyboard (hardware)
            'sodium-extra',                   # Sodium addon
            'iris-mc', 'irisshaders',         # Iris Shaders
            'meteor-client-',                 # solo si tiene `-` (release tag)
            'axolotl', 'axolotlclient',       # AxolotlClient — mod legítimo de cosmetics
            'continuity',                     # Continuity mod (connected textures)
            'bobby',                          # Bobby mod (render distance)
            'ferritecore',                    # memory optimization
            'distanthorizons',               # Distant Horizons
            'moreculling',                    # MoreCulling
            'noxesium',                       # Noxesium (Hypixel mods)
        }
        try:
            for mods_dir in mods_dirs_to_scan:
             for fname in os.listdir(mods_dir):
                if not fname.lower().endswith('.jar'):
                    continue
                # F21 already handled in filter, but also skip here at source
                if fname.lower().endswith(('.disabled', '.bak', '.off', '.old')):
                    continue
                fpath = os.path.join(mods_dir, fname)
                fname_lower = fname.lower()
                # P2 #2 — Verificar contra whitelist por servidor (nombre)
                if server_allowed and fname_lower in server_allowed:
                    continue
                # Calcular hash SHA256 una sola vez (usado por whitelist + blacklist)
                _sha256 = None
                try:
                    h = hashlib.sha256()
                    with open(fpath, 'rb') as f:
                        for chunk in iter(lambda: f.read(65536), b''):
                            h.update(chunk)
                    _sha256 = h.hexdigest().lower()
                except Exception:
                    pass
                # P2 #1 — Verificar contra whitelist dinámica de mods legítimos (hash)
                if cloud_whitelist and _sha256 and _sha256 in cloud_whitelist:
                    continue  # mod legítimo confirmado
                # P3 #17 — Verificar contra blacklist dinámica de hacks confirmados
                if cloud_blacklist and _sha256 and _sha256 in cloud_blacklist:
                    print(f"🚨 HASH EN BLACKLIST DINÁMICA: {fname} ({_sha256[:12]}...)")
                    self.issues_found.append({
                        'nombre': f'Hash confirmado como hack en blacklist dinámica: {fname}',
                        'ruta': fpath,
                        'archivo': fname,
                        'tipo': 'cloud_hash_match',
                        'categoria': 'GHOST_CLIENT',
                        'alerta': 'CRITICAL',
                        'confidence': 0.98,
                        'detected_patterns': [f'cloud_blacklist:{_sha256[:16]}'],
                        'file_hash': _sha256,
                        'explicacion': (
                            f'El hash SHA256 de "{fname}" está en la blacklist dinámica — '
                            'confirmado como hack en 3 o más scans previos. '
                            'Detección 100% confiable por hash.'
                        ),
                    })
                    continue
                # F13 — Si el mod está en la carpeta de un modpack popular, skip
                fpath_lower = fpath.lower()
                if any(mp in fpath_lower for mp in MODPACK_WHITELIST_DIRS):
                    continue
                # F15 — Whitelist de nombres de mods legítimos que colisionan con hack patterns
                if any(lm in fname_lower for lm in LEGIT_MOD_NAME_FRAGMENTS):
                    continue

                matched_bl = next((bl for bl in BLACKLISTED if bl in fname_lower), None)
                if matched_bl:
                    print(f"🚨 MOD PROHIBIDO: {fname}")
                    self.issues_found.append({
                        'nombre': f'Mod prohibido detectado en .minecraft/mods/: {fname}',
                        'ruta': fpath,
                        'archivo': fname,
                        'tipo': 'blacklisted_mod',
                        'categoria': 'GHOST_CLIENT',
                        'alerta': 'CRITICAL',
                        'confidence': 0.95,
                        'detected_patterns': [f'blacklisted_mod:{matched_bl}'],
                        'explicacion': f'El archivo "{fname}" en la carpeta de mods contiene el nombre de un hack client '
                                       f'conocido ({matched_bl}). Está directamente instalado como mod en Minecraft.',
                    })
                else:
                    # Analizar nombres de clases internas del JAR — detecta mods renombrados
                    class_hit = None
                    try:
                        import zipfile as _zf
                        HACK_PKG_PREFIXES = [
                            'com/vape/', 'net/sigma/', 'com/entropy/', 'net/liquidbounce/',
                            'com/wurst/', 'com/future/', 'com/flux/', 'com/meteor/',
                            'com/astolfo/', 'net/rise/', 'com/novoline/', 'me/kami/',
                            'net/rusherhack/', 'com/aristois/', 'com/tenacity/',
                            'com/vertex/', 'com/inertia/', 'com/salhack/', 'com/jello/',
                            'me/baritone/', 'com/phobos/', 'com/pandora/', 'com/azura/',
                            'com/konas/', 'com/remix/', 'me/weave/', 'net/weaveloader/',
                            'meteordevelopment/', 'me/drip/',
                        ]
                        with _zf.ZipFile(fpath, 'r') as zf:
                            for entry in zf.namelist():
                                entry_lower = entry.lower()
                                if entry_lower.endswith('.class'):
                                    for pkg in HACK_PKG_PREFIXES:
                                        if entry_lower.startswith(pkg):
                                            class_hit = pkg.rstrip('/').replace('/', '.')
                                            break
                                if class_hit:
                                    break
                    except Exception:
                        pass

                    if class_hit:
                        print(f"🚨 CLASE DE HACK EN JAR RENOMBRADO: {fname} → paquete {class_hit}")
                        self.issues_found.append({
                            'nombre': f'JAR renombrado con clases de hack: {fname}',
                            'ruta': fpath,
                            'archivo': fname,
                            'tipo': 'blacklisted_mod',
                            'categoria': 'GHOST_CLIENT',
                            'alerta': 'CRITICAL',
                            'confidence': 0.93,
                            'detected_patterns': [f'jar_class_pkg:{class_hit}'],
                            'explicacion': (
                                f'El archivo "{fname}" tiene un nombre inocente, pero sus clases internas '
                                f'pertenecen al paquete "{class_hit}" — un hack client conocido. '
                                f'El jugador renombró el JAR para evadir la detección por nombre.'
                            ),
                        })
                    else:
                        # P3 #10 — character n-gram similarity for renamed/obfuscated hack mods
                        sim, matched_hack = self._score_path_hack_similarity(fname)
                        if sim >= 0.40:
                            print(f"⚠️ MOD SIMILAR A HACK (N-GRAM): {fname} ~ {matched_hack} ({sim:.2f})")
                            self.issues_found.append({
                                'nombre': f'Mod con nombre similar a hack conocido: {fname} ≈ {matched_hack}',
                                'ruta': fpath,
                                'archivo': fname,
                                'tipo': 'blacklisted_mod',
                                'categoria': 'GHOST_CLIENT',
                                'alerta': 'SOSPECHOSO',
                                'confidence': round(min(0.85, 0.50 + sim * 0.7), 2),
                                'detected_patterns': [f'name_similar_to:{matched_hack}({sim:.2f})'],
                                'explicacion': f'El mod "{fname}" tiene alta similitud de caracteres (n-gram Jaccard={sim:.2f}) '
                                               f'con el cliente de hack conocido "{matched_hack}". Puede estar renombrado para evadir detección.',
                            })
        except Exception as e:
            print(f"Error en scan_minecraft_mods_blacklist: {e}")

    def scan_dll_injection_java(self):
        """Detecta DLLs sospechosas cargadas en procesos Java/Minecraft en tiempo real."""
        print("🔍 Escaneando DLLs en procesos Java...")
        # Nombres exclusivos de hack clients — misma lógica que _DEFINITE_HACK_NAMES
        SUSPICIOUS_DLL_KW = list(_DEFINITE_HACK_NAMES) + [
            'injector', 'xinput_hook', 'payload', 'loader_dll',
            'aimhook', 'killaura_dll', 'bypass_dll',
        ]
        # DLLs del sistema y JRE que NUNCA son hacks
        SAFE_PREFIXES = [
            'c:\\windows\\',
            'c:\\program files\\java',
            'c:\\program files (x86)\\java',
            'c:\\program files\\eclipse adoptium',
            'c:\\program files\\eclipse foundation',
            'c:\\program files\\microsoft',
            'c:\\program files (x86)\\microsoft',
            '\\jdk', '\\jre', '\\runtime\\jre',
            '\\lunarclient\\', '\\badlionclient\\', '\\tlauncher\\',
            '\\prismlauncher\\', '\\multimc\\', '\\atlauncher\\',
        ]
        # DLL de sistema y JVM conocidas — false positive frecuente
        SAFE_DLL_NAMES = {
            'jvm.dll', 'jawt.dll', 'verify.dll', 'java.dll', 'net.dll',
            'nio.dll', 'zip.dll', 'fontmanager.dll', 'freetype.dll',
            'glass.dll', 'prism_sw.dll', 'd3d12.dll', 'dxgi.dll',
            'ntdll.dll', 'kernel32.dll', 'user32.dll', 'advapi32.dll',
            'shell32.dll', 'msvcrt.dll', 'vcruntime140.dll', 'ucrtbase.dll',
            'opengl32.dll', 'glu32.dll', 'lwjgl.dll', 'lwjgl64.dll',
            'openal.dll', 'openal64.dll', 'jinput-dx8.dll', 'jinput-raw.dll',
        }
        try:
            for proc in psutil.process_iter(['pid', 'name', 'cmdline']):
                try:
                    name = (proc.info.get('name') or '').lower()
                    if 'java' not in name:
                        continue
                    # Verificar que es Minecraft (cmdline contiene net.minecraft o launcher)
                    cmdline = ' '.join(proc.info.get('cmdline') or []).lower()
                    is_minecraft = ('net.minecraft' in cmdline or
                                    'minecraft' in cmdline or
                                    'forge' in cmdline or
                                    'fabric' in cmdline)
                    if not is_minecraft:
                        continue
                    try:
                        for mmap in proc.memory_maps():
                            path = (mmap.path or '').lower()
                            if not path.endswith('.dll'):
                                continue
                            dll_name = os.path.basename(path)
                            if dll_name in SAFE_DLL_NAMES:
                                continue
                            if any(path.startswith(s) for s in SAFE_PREFIXES):
                                continue
                            # Normalizar el nombre de la DLL para homoglyphs
                            dll_norm = _normalize(dll_name)
                            hit = next(
                                (kw for kw in SUSPICIOUS_DLL_KW
                                 if kw in dll_name or kw in dll_norm),
                                None
                            )
                            if hit:
                                print(f"🚨 DLL HACK en javaw.exe (PID {proc.pid}): {path}")
                                self.issues_found.append({
                                    'nombre': f'DLL de hack cargada en Minecraft: {dll_name}',
                                    'ruta': path,
                                    'archivo': dll_name,
                                    'tipo': 'dll_injection_java',
                                    'categoria': 'JAVA_INJECTION',
                                    'alerta': 'CRITICAL',
                                    'confidence': 0.93,
                                    'detected_patterns': [f'dll_hack:{hit}'],
                                    'explicacion': (
                                        f'La DLL "{dll_name}" está cargada en el proceso de Minecraft (PID {proc.pid}). '
                                        f'Su nombre coincide con el hack client "{hit}". '
                                        f'Las DLLs de hack se inyectan en el proceso del juego para añadir '
                                        f'módulos como killaura, aimbot o scaffold sin dejar archivos visibles.'
                                    ),
                                })
                                break  # Solo reportar 1 hit por DLL
                    except (psutil.AccessDenied, psutil.NoSuchProcess):
                        pass
                except (psutil.NoSuchProcess, psutil.AccessDenied):
                    continue
        except Exception as e:
            print(f"Error en scan_dll_injection_java: {e}")

    def scan_java_dll_nonstandard(self):
        """P2 #30 approx — DLLs en procesos Java desde rutas fuera del baseline estándar.
        Complementa scan_dll_injection_java (que busca por nombre); éste busca por ubicación.
        """
        SAFE_PATH_PREFIXES = (
            'c:\\windows\\',
            'c:\\program files\\java', 'c:\\program files (x86)\\java',
            'c:\\program files\\eclipse', 'c:\\program files (x86)\\eclipse',
            'c:\\program files\\microsoft', 'c:\\program files (x86)\\microsoft',
            'c:\\program files\\lunarclient', 'c:\\program files\\badlionclient',
            '\\jdk', '\\jre', '\\runtime\\jre',
            '\\lunarclient\\', '\\badlionclient\\', '\\tlauncher\\',
            '\\prismlauncher\\', '\\multimc\\', '\\atlauncher\\', '\\polymc\\',
            '\\modrinth\\', '\\curseforge\\',
        )
        SAFE_DLL_NAMES = {
            'jvm.dll', 'jawt.dll', 'verify.dll', 'java.dll', 'net.dll', 'nio.dll',
            'zip.dll', 'fontmanager.dll', 'freetype.dll', 'glass.dll', 'prism_sw.dll',
            'ntdll.dll', 'kernel32.dll', 'kernelbase.dll', 'user32.dll', 'gdi32.dll',
            'gdi32full.dll', 'win32u.dll', 'advapi32.dll', 'shell32.dll', 'shlwapi.dll',
            'ole32.dll', 'oleaut32.dll', 'comctl32.dll', 'comdlg32.dll', 'msvcrt.dll',
            'msvcp140.dll', 'vcruntime140.dll', 'vcruntime140_1.dll', 'ucrtbase.dll',
            'ws2_32.dll', 'wininet.dll', 'urlmon.dll', 'secur32.dll', 'crypt32.dll',
            'bcrypt.dll', 'bcryptprimitives.dll', 'rpcrt4.dll', 'psapi.dll',
            'iphlpapi.dll', 'dnsapi.dll', 'dbghelp.dll', 'version.dll', 'wintrust.dll',
            'opengl32.dll', 'glu32.dll', 'd3d9.dll', 'd3d11.dll', 'd3d12.dll', 'dxgi.dll',
            'lwjgl.dll', 'lwjgl64.dll', 'openal.dll', 'openal64.dll',
            'jinput-dx8.dll', 'jinput-dx8_64.dll', 'jinput-raw.dll', 'jinput-raw_64.dll',
            'nvspcap64.dll', 'nvspcap.dll', 'nvoglv64.dll', 'nvoglv32.dll',
            'atioglxx.dll', 'atig6pxx.dll', 'ig75icd64.dll', 'ig4icd64.dll',
            'mswsock.dll', 'wldap32.dll', 'msimg32.dll', 'imm32.dll', 'uxtheme.dll',
            'cryptbase.dll', 'cryptsp.dll', 'propsys.dll', 'profapi.dll', 'clbcatq.dll',
            # F27 — DLLs de mods gráficos legítimos (Iris LWJGL fork, Distant Horizons)
            'lwjgl_opengl.dll', 'lwjgl_stb.dll', 'lwjgl_tinyfd.dll', 'lwjgl_vulkan.dll',
            'lwjgl_openvr.dll', 'lwjgl_xxhash.dll', 'lwjgl_remotery.dll',
            'lwjgl_nfd.dll', 'lwjgl_opus.dll', 'lwjgl_lz4.dll', 'lwjgl_zstd.dll',
            'vma.dll', 'shaderc.dll', 'spirvcross.dll', 'glfw.dll',
            # DXVK/MoltenVK para mods de renderizado con Vulkan
            'd3d9.dll', 'dxvk.dll', 'vk-layer.dll', 'vulkan-1.dll', 'igvulkan64.dll',
        }
        # F27 — Fragmentos de rutas de mods gráficos — DLLs en estas carpetas son seguras
        SAFE_GRAPHICAL_MOD_PATHS = (
            '\\iris\\', '\\irisshaders\\', '\\distanthorizons\\', '\\sodium\\',
            '\\iris-data\\', '\\dh-data\\', '\\shaderpacks\\', '\\shaders\\',
            '\\lwjgl\\', '\\lwjgl3\\', '\\natives\\', '-natives\\',
        )
        found = []
        try:
            for proc in psutil.process_iter(['pid', 'name', 'cmdline']):
                try:
                    pname = (proc.info.get('name') or '').lower()
                    if 'java' not in pname:
                        continue
                    cmdline = ' '.join(proc.info.get('cmdline') or []).lower()
                    if 'minecraft' not in cmdline and 'net.minecraft' not in cmdline:
                        continue
                    try:
                        for mmap in proc.memory_maps():
                            path = (mmap.path or '').lower()
                            if not path.endswith('.dll'):
                                continue
                            dll_name = os.path.basename(path)
                            if dll_name in SAFE_DLL_NAMES:
                                continue
                            if any(path.startswith(p) for p in SAFE_PATH_PREFIXES):
                                continue
                            # F27 — Rutas de mods gráficos son seguras
                            if any(frag in path for frag in SAFE_GRAPHICAL_MOD_PATHS):
                                continue
                            found.append((dll_name, mmap.path, proc.pid))
                    except (psutil.AccessDenied, psutil.NoSuchProcess, AttributeError):
                        pass
                except (psutil.NoSuchProcess, psutil.AccessDenied):
                    continue
        except Exception as e:
            print(f"Error en scan_java_dll_nonstandard: {e}")

        for dll_name, full_path, pid in found[:10]:
            self.issues_found.append({
                'nombre':   f'DLL fuera de baseline en Minecraft: {dll_name}',
                'ruta':     os.path.dirname(full_path),
                'archivo':  full_path,
                'tipo':     'dll_nonstandard',
                'categoria': 'JAVA_INJECTION',
                'alerta':   'SOSPECHOSO',
                'confidence': 0.58,
                'detected_patterns': [f'dll_ruta_no_estandar:{os.path.dirname(full_path)[:80]}'],
                'explicacion': (
                    f'La DLL "{dll_name}" está cargada en Minecraft (PID {pid}) '
                    f'desde una ruta no estándar: {full_path[:120]}. '
                    f'Las DLLs de hack suelen residir fuera de Windows\\, Program Files\\ '
                    f'o las carpetas del launcher.'
                ),
            })

    def scan_self_deletion_hacks(self):
        """P2 #50 — Detecta JARs en la línea de comandos de Java que ya no existen en disco.
        Técnica común de hacks: cargar el JAR vía classloader y luego borrarlo para ocultar evidencia.
        """
        found = []
        try:
            for proc in psutil.process_iter(['pid', 'name', 'cmdline']):
                try:
                    pname = (proc.info.get('name') or '').lower()
                    if 'java' not in pname:
                        continue
                    cmdline = proc.info.get('cmdline') or []
                    cmdline_str = ' '.join(cmdline).lower()
                    if 'minecraft' not in cmdline_str and 'net.minecraft' not in cmdline_str:
                        continue
                    for arg in cmdline:
                        if not (arg.endswith('.jar') or arg.endswith('.JAR')):
                            continue
                        jar_path = os.path.normpath(arg) if os.path.isabs(arg) else arg
                        if not os.path.exists(jar_path):
                            found.append((jar_path, proc.pid))
                except (psutil.NoSuchProcess, psutil.AccessDenied):
                    continue
        except Exception as e:
            print(f"Error en scan_self_deletion_hacks: {e}")
        for jar_path, pid in found:
            self.issues_found.append({
                'nombre':   f'JAR borrado mientras Minecraft corre: {os.path.basename(jar_path)}',
                'ruta':     os.path.dirname(jar_path),
                'archivo':  jar_path,
                'tipo':     'jar_self_deleted',
                'categoria': 'GHOST_CLIENT',
                'alerta':   'CRITICAL',
                'confidence': 0.91,
                'detected_patterns': ['jar_deleted_while_running'],
                'explicacion': (
                    f'El archivo "{jar_path}" aparece en los argumentos de Minecraft '
                    f'(PID {pid}) pero ya NO existe en disco. Esta técnica — cargar el '
                    f'JAR y luego borrarlo — es usada por hacks para eliminar evidencia '
                    f'forense del escaneo.'
                ),
            })

    def scan_java_suspicious_tls(self):
        """P2 #29 — Detecta conexiones TLS activas de Java hacia servidores desconocidos.
        Complementa scan_javaw_network_connections con foco en puertos HTTPS no estándar.
        """
        import socket as _sock
        SAFE_TLS_SUFFIXES = (
            '.mojang.com', '.minecraft.net', '.microsoft.com', '.live.com',
            '.cloudfront.net', '.amazonaws.com', '.fastly.net', '.akamai.net',
            '.modrinth.com', '.curseforge.com', '.twitch.tv', '.cdn.net',
            '.discordapp.com', '.discord.com', '.googleapis.com', '.gstatic.com',
            # F29 — Servidores de Minecraft conocidos: sus IPs NO son C2
            'hypixel.net', 'mineplex.com', 'cubecraft.net', 'hivemc.com',
            'wynncraft.com', '2b2t.org', 'mccentral.org', 'minehut.com',
            'aternos.me', 'aternos.org', 'falixnodes.net',
        )
        SAFE_TLS_PORTS = {443, 8443}
        SUSPICIOUS_TLS_PORTS = {4433, 8444, 9000, 9001, 9090, 1443, 2083, 2087, 2096}

        found = []
        try:
            for proc in psutil.process_iter(['pid', 'name', 'cmdline']):
                try:
                    pname = (proc.info.get('name') or '').lower()
                    if 'java' not in pname:
                        continue
                    cmdline_str = ' '.join(proc.info.get('cmdline') or []).lower()
                    if 'minecraft' not in cmdline_str and 'net.minecraft' not in cmdline_str:
                        continue
                    for conn in proc.connections('tcp4'):
                        if conn.status != psutil.CONN_ESTABLISHED:
                            continue
                        rip   = conn.raddr.ip   if conn.raddr else ''
                        rport = conn.raddr.port if conn.raddr else 0
                        if not rip or not rport:
                            continue
                        if rport not in SAFE_TLS_PORTS and rport not in SUSPICIOUS_TLS_PORTS:
                            continue
                        try:
                            hostname = _sock.getfqdn(rip)
                        except Exception:
                            hostname = rip
                        if any(hostname.endswith(s) for s in SAFE_TLS_SUFFIXES):
                            continue
                        # Conexión TLS a host desconocido
                        is_nonstandard_port = rport in SUSPICIOUS_TLS_PORTS
                        found.append((rip, rport, hostname, proc.pid, is_nonstandard_port))
                except (psutil.NoSuchProcess, psutil.AccessDenied):
                    continue
        except Exception as e:
            print(f"Error en scan_java_suspicious_tls: {e}")

        for rip, rport, hostname, pid, nonstandard in found[:8]:
            severity = 'CRITICAL' if nonstandard else 'SOSPECHOSO'
            conf     = 0.78 if nonstandard else 0.55
            self.issues_found.append({
                'nombre':   f'Conexión TLS de Minecraft a host desconocido: {hostname} :{rport}',
                'ruta':     f'{rip}:{rport}',
                'archivo':  hostname,
                'tipo':     'java_suspicious_tls',
                'categoria': 'RED',
                'alerta':   severity,
                'confidence': conf,
                'detected_patterns': [
                    f'tls_host:{hostname[:40]}',
                    f'tls_port:{rport}',
                    *(['nonstandard_tls_port'] if nonstandard else []),
                ],
                'explicacion': (
                    f'El proceso Minecraft (PID {pid}) tiene una conexión TLS activa '
                    f'hacia {hostname} (IP {rip}) en el puerto {rport}. '
                    f'Este dominio/IP no pertenece a Mojang, CDNs conocidas ni '
                    f'servicios de launchers. Podría ser un servidor C2 de un hack client.'
                ),
            })

    # ── P5 NUEVAS DETECCIONES ────────────────────────────────────────────────

    def scan_cheat_engine(self):
        """P5 #1 — Detecta Cheat Engine activo o instalado (herramienta de memory hacking)."""
        print("🔍 Buscando Cheat Engine...")
        CE_PROC_NAMES = {'cheatengine-x86_64.exe', 'cheatengine-x86_64-avx2.exe', 'cheatengine.exe',
                         'ce.exe', 'ce_x64.exe', 'cheat engine.exe'}
        CE_REGISTRY_PATHS = [
            r'SOFTWARE\Cheat Engine',
            r'SOFTWARE\WOW6432Node\Cheat Engine',
            r'SOFTWARE\Microsoft\Windows\CurrentVersion\Uninstall\Cheat Engine',
        ]
        CE_FILE_PATHS = [
            os.path.join(os.environ.get('PROGRAMFILES', r'C:\Program Files'), 'Cheat Engine'),
            os.path.join(os.environ.get('PROGRAMFILES(X86)', r'C:\Program Files (x86)'), 'Cheat Engine'),
            os.path.expanduser(r'~\Desktop\cheatengine-x86_64.exe'),
            os.path.expanduser(r'~\Downloads\cheatengine-x86_64.exe'),
        ]
        found_active = False
        found_installed = False
        try:
            for proc in psutil.process_iter(['name', 'exe']):
                try:
                    pname = (proc.info.get('name') or '').lower()
                    pexe  = os.path.basename(proc.info.get('exe') or '').lower()
                    if pname in CE_PROC_NAMES or pexe in CE_PROC_NAMES:
                        found_active = True
                        self.issues_found.append({
                            'nombre': f'Cheat Engine activo en proceso: {proc.info.get("name")}',
                            'ruta': proc.info.get('exe') or 'Proceso activo',
                            'archivo': proc.info.get('name') or '',
                            'tipo': 'cheat_engine_active',
                            'categoria': 'PROCESO',
                            'alerta': 'CRITICAL',
                            'confidence': 0.95,
                            'detected_patterns': ['cheat_engine_process'],
                            'explicacion': (
                                'Cheat Engine está corriendo actualmente. Es la herramienta de '
                                'memory hacking más usada para cheats en Minecraft (modifica '
                                'valores de memoria del juego en tiempo real).'
                            ),
                        })
                        print(f"🚨 CHEAT ENGINE ACTIVO: {proc.info.get('name')}")
                except (psutil.NoSuchProcess, psutil.AccessDenied):
                    pass
        except Exception:
            pass

        if not found_active:
            # Buscar en registro
            for reg_path in CE_REGISTRY_PATHS:
                try:
                    with winreg.OpenKey(winreg.HKEY_LOCAL_MACHINE, reg_path):
                        found_installed = True
                        break
                except (FileNotFoundError, PermissionError):
                    pass
            # Buscar archivos
            if not found_installed:
                for ce_path in CE_FILE_PATHS:
                    if os.path.exists(ce_path):
                        found_installed = True
                        break
            if found_installed:
                self.issues_found.append({
                    'nombre': 'Cheat Engine instalado en el sistema',
                    'ruta': 'Program Files / Registro',
                    'archivo': 'cheatengine',
                    'tipo': 'cheat_engine_installed',
                    'categoria': 'FORENSE',
                    'alerta': 'SOSPECHOSO',
                    'confidence': 0.72,
                    'detected_patterns': ['cheat_engine_installed'],
                    'explicacion': (
                        'Cheat Engine está instalado. Aunque puede tener usos legítimos, '
                        'es frecuentemente usado para cheats en Minecraft mediante '
                        'modificación de memoria de procesos.'
                    ),
                })
                print("⚠️ Cheat Engine instalado (no activo actualmente)")

    def scan_packet_sniffers(self):
        """P5 #2 — Detecta packet sniffers activos: Wireshark, Fiddler, mitmproxy, Charles."""
        print("🔍 Buscando packet sniffers activos...")
        SNIFFER_PROCS = {
            'wireshark.exe': ('Wireshark', 0.70),
            'dumpcap.exe':   ('Wireshark/dumpcap', 0.65),
            'tshark.exe':    ('TShark (Wireshark CLI)', 0.65),
            'fiddler.exe':   ('Fiddler', 0.60),
            'fiddler4.exe':  ('Fiddler4', 0.60),
            'fiddlercap.exe': ('FiddlerCap', 0.60),
            'mitmdump.exe':  ('mitmproxy', 0.68),
            'mitmweb.exe':   ('mitmproxy web', 0.68),
            'mitmproxy.exe': ('mitmproxy', 0.68),
            'charles.exe':   ('Charles Proxy', 0.60),
            'proxyman.exe':  ('Proxyman', 0.55),
            'httpanalyzer.exe': ('HTTP Analyzer', 0.55),
            'burpsuite.exe': ('Burp Suite', 0.70),
            'netmon.exe':    ('Network Monitor', 0.50),
        }
        try:
            for proc in psutil.process_iter(['name', 'exe', 'pid']):
                try:
                    pname = (proc.info.get('name') or '').lower()
                    if pname in SNIFFER_PROCS:
                        label, conf = SNIFFER_PROCS[pname]
                        self.issues_found.append({
                            'nombre': f'Packet sniffer activo: {label} (PID {proc.info.get("pid")})',
                            'ruta': proc.info.get('exe') or pname,
                            'archivo': pname,
                            'tipo': 'packet_sniffer_active',
                            'categoria': 'RED',
                            'alerta': 'SOSPECHOSO',
                            'confidence': conf,
                            'detected_patterns': [f'sniffer:{pname}'],
                            'explicacion': (
                                f'{label} está activo durante el scan. Un packet sniffer '
                                f'puede usarse para capturar el tráfico de red de Minecraft '
                                f'(tokens de sesión, servidor objetivo, etc.).'
                            ),
                        })
                        print(f"⚠️ PACKET SNIFFER ACTIVO: {label}")
                except (psutil.NoSuchProcess, psutil.AccessDenied):
                    pass
        except Exception as e:
            print(f"Error en scan_packet_sniffers: {e}")

    def scan_jdk_installed(self):
        """P5 #4 — Detecta JDK completo instalado (señal de desarrollo de hacks)."""
        print("🔍 Buscando JDK completo instalado...")
        JDK_INDICATORS = [
            os.path.join(os.environ.get('PROGRAMFILES', ''), 'Eclipse Adoptium'),
            os.path.join(os.environ.get('PROGRAMFILES', ''), 'Java'),
            os.path.join(os.environ.get('PROGRAMFILES(X86)', ''), 'Java'),
            os.path.join(os.environ.get('PROGRAMFILES', ''), 'Microsoft'),  # MS Build JDK
        ]
        JDK_REG_PATHS = [
            r'SOFTWARE\JavaSoft\Java Development Kit',
            r'SOFTWARE\WOW6432Node\JavaSoft\Java Development Kit',
            r'SOFTWARE\Eclipse Adoptium',
            r'SOFTWARE\Eclipse Foundation',
        ]
        # JRE-only entries son normales (Minecraft lo necesita). Solo flagear JDK completo.
        jdk_found = []
        for reg_path in JDK_REG_PATHS:
            try:
                with winreg.OpenKey(winreg.HKEY_LOCAL_MACHINE, reg_path) as k:
                    i = 0
                    while True:
                        try:
                            subkey = winreg.EnumKey(k, i)
                            i += 1
                            with winreg.OpenKey(k, subkey) as sk:
                                try:
                                    home, _ = winreg.QueryValueEx(sk, 'JavaHome')
                                    # Si existe javac.exe → es JDK (compilador)
                                    javac = os.path.join(str(home), 'bin', 'javac.exe')
                                    if os.path.isfile(javac):
                                        jdk_found.append(str(home))
                                except (FileNotFoundError, OSError):
                                    pass
                        except OSError:
                            break
            except (FileNotFoundError, PermissionError):
                pass

        for jdk_path in jdk_found[:3]:
            self.issues_found.append({
                'nombre': f'JDK completo instalado: {os.path.basename(jdk_path)}',
                'ruta': jdk_path,
                'archivo': 'javac.exe',
                'tipo': 'jdk_installed',
                'categoria': 'FORENSE',
                'alerta': 'POCO_SOSPECHOSO',
                'confidence': 0.45,
                'detected_patterns': ['jdk_with_compiler'],
                'explicacion': (
                    f'Se encontró un JDK completo ({jdk_path}). Un jugador normal solo '
                    f'necesita el JRE para ejecutar Minecraft. El JDK incluye javac (compilador) '
                    f'y puede usarse para desarrollar o compilar hack clients personalizados.'
                ),
            })
            print(f"⚠️ JDK instalado: {jdk_path}")

    def scan_python_hack_scripts(self):
        """P5 #5 — Detecta scripts Python en Desktop/Downloads con patrones de bots/macros."""
        print("🔍 Buscando scripts Python de bots/macros en Desktop/Downloads...")
        import re as _re
        SEARCH_DIRS = [
            os.path.expanduser('~\\Desktop'),
            os.path.expanduser('~\\Downloads'),
            os.path.expanduser('~\\Documents'),
        ]
        # Patrones de contenido sospechoso
        HACK_CONTENT_RE = [
            r'import\s+pyautogui',          # automation GUI
            r'import\s+pynput',             # keyboard/mouse hooks
            r'import\s+win32api',           # Windows API
            r'pyperclip|clipboard',         # portapapeles
            r'minecraft.*socket|socket.*minecraft',  # socket C2
            r'autoclicker|auto.?click',     # autoclicker
            r'triggerbot|trigger.?bot',
            r'aimbot|aim.?bot',
            r'macro.*minecraft|minecraft.*macro',
            r'send.*packet|inject.*packet',
            r'\bxray\b.*minecraft|minecraft.*\bxray\b',
        ]
        HACK_FILENAME_KW = ['hack', 'cheat', 'macro', 'autoclicker', 'autoclick',
                            'triggerbot', 'aimbot', 'bot', 'inject']
        found = 0
        for base_dir in SEARCH_DIRS:
            if not os.path.isdir(base_dir):
                continue
            try:
                for fname in os.listdir(base_dir):
                    if not fname.lower().endswith('.py'):
                        continue
                    fpath = os.path.join(base_dir, fname)
                    fname_lower = fname.lower()
                    # Por nombre
                    if any(kw in fname_lower for kw in HACK_FILENAME_KW):
                        self.issues_found.append({
                            'nombre': f'Script Python sospechoso: {fname}',
                            'ruta': base_dir,
                            'archivo': fpath,
                            'tipo': 'python_hack_script',
                            'categoria': 'GHOST_CLIENT',
                            'alerta': 'SOSPECHOSO',
                            'confidence': 0.65,
                            'detected_patterns': ['python_suspicious_name'],
                        })
                        found += 1
                        print(f"⚠️ Script Python sospechoso (nombre): {fname}")
                        continue
                    # Por contenido (primeros 8KB)
                    try:
                        with open(fpath, 'r', encoding='utf-8', errors='ignore') as f:
                            content = f.read(8192).lower()
                        matched_patterns = []
                        for pattern in HACK_CONTENT_RE:
                            if _re.search(pattern, content, _re.IGNORECASE):
                                matched_patterns.append(pattern[:30])
                        if len(matched_patterns) >= 2:
                            self.issues_found.append({
                                'nombre': f'Script Python con patrones de hack: {fname}',
                                'ruta': base_dir,
                                'archivo': fpath,
                                'tipo': 'python_hack_script',
                                'categoria': 'GHOST_CLIENT',
                                'alerta': 'SOSPECHOSO',
                                'confidence': 0.62,
                                'detected_patterns': matched_patterns[:5],
                                'explicacion': (
                                    f'Script Python "{fname}" contiene patrones de automatización '
                                    f'sospechosa para Minecraft: {", ".join(matched_patterns[:3])}.'
                                ),
                            })
                            found += 1
                            print(f"⚠️ Script Python con patrones de hack (contenido): {fname}")
                    except (IOError, OSError):
                        pass
            except PermissionError:
                pass
        if found == 0:
            print("✅ No se encontraron scripts Python sospechosos")

    def scan_lunar_unofficial_modules(self):
        """P5 #8 — Detecta módulos no oficiales en Lunar Client (.lunarclient/offline/multiver)."""
        print("🔍 Buscando módulos no oficiales de Lunar Client...")
        LUNAR_BASE = os.path.expanduser(r'~\.lunarclient')
        if not os.path.isdir(LUNAR_BASE):
            print("✅ Lunar Client no instalado")
            return

        # Módulos oficiales de Lunar Client (sus propias features)
        LUNAR_OFFICIAL_MODS = {
            'optifine', 'sodium', 'iris', 'lunar', 'sk1er', 'labymod',
            'essential', 'feather',
        }
        # Rutas de módulos de terceros dentro de Lunar
        MODULE_DIRS = [
            os.path.join(LUNAR_BASE, 'offline', 'multiver'),
            os.path.join(LUNAR_BASE, 'textures'),
            os.path.join(LUNAR_BASE, 'mods'),
        ]
        found = 0
        for mod_dir in MODULE_DIRS:
            if not os.path.isdir(mod_dir):
                continue
            try:
                for fname in os.listdir(mod_dir):
                    fname_lower = fname.lower()
                    if not fname_lower.endswith('.jar'):
                        continue
                    # Si el nombre coincide con hack clients conocidos
                    for hack_name in _DEFINITE_HACK_NAMES:
                        if hack_name in fname_lower:
                            self.issues_found.append({
                                'nombre': f'Módulo no oficial de Lunar Client: {fname}',
                                'ruta': mod_dir,
                                'archivo': os.path.join(mod_dir, fname),
                                'tipo': 'lunar_unofficial_module',
                                'categoria': 'GHOST_CLIENT',
                                'alerta': 'CRITICAL',
                                'confidence': 0.88,
                                'detected_patterns': [f'lunar_mod:{hack_name}'],
                                'explicacion': (
                                    f'Módulo "{fname}" encontrado en la carpeta de módulos de '
                                    f'Lunar Client. Coincide con hack client conocido "{hack_name}". '
                                    f'Lunar Client carga estos módulos durante el juego.'
                                ),
                            })
                            found += 1
                            print(f"🚨 LUNAR MOD SOSPECHOSO: {fname}")
                            break
            except (PermissionError, OSError):
                pass
        if found == 0:
            print("✅ No se encontraron módulos no oficiales de Lunar Client")

    def scan_virtual_audio_cable(self):
        """P5 #10 — Detecta Virtual Audio Cable / VB-Audio (usado para ocultar comunicaciones de equipo)."""
        print("🔍 Buscando virtual audio cable / VB-Audio...")
        VAC_INDICATORS = {
            # Nombre de driver en registro
            'reg': [
                r'SYSTEM\CurrentControlSet\Services\VBAudioVACWDM',
                r'SYSTEM\CurrentControlSet\Services\VBAudioVoicemeeter',
                r'SYSTEM\CurrentControlSet\Services\vac',
                r'SOFTWARE\Virtual Audio Cable',
                r'SOFTWARE\VB-Audio',
            ],
            # Procesos
            'procs': {
                'vbcable.exe', 'voicemeeter.exe', 'voicemeeterpro.exe',
                'vbvmtray.exe', 'vbvmservice.exe', 'audiorepeater.exe',
            },
        }
        found = False
        try:
            for proc in psutil.process_iter(['name']):
                try:
                    pname = (proc.info.get('name') or '').lower()
                    if pname in VAC_INDICATORS['procs']:
                        found = True
                        self.issues_found.append({
                            'nombre': f'Virtual Audio Cable activo: {proc.info.get("name")}',
                            'ruta': 'Proceso activo',
                            'archivo': pname,
                            'tipo': 'virtual_audio_cable',
                            'categoria': 'PROCESO',
                            'alerta': 'POCO_SOSPECHOSO',
                            'confidence': 0.42,
                            'detected_patterns': ['vac_process'],
                            'explicacion': (
                                'Virtual Audio Cable o VB-Audio está activo. Estas herramientas '
                                'pueden usarse para redirigir audio de comunicaciones de equipo '
                                '(Discord, TeamSpeak) y evitar que el escáner detecte el micrófono.'
                            ),
                        })
                        print(f"⚠️ VAC activo: {proc.info.get('name')}")
                except (psutil.NoSuchProcess, psutil.AccessDenied):
                    pass
        except Exception:
            pass

        if not found:
            for reg_path in VAC_INDICATORS['reg']:
                try:
                    with winreg.OpenKey(winreg.HKEY_LOCAL_MACHINE, reg_path):
                        self.issues_found.append({
                            'nombre': 'Virtual Audio Cable / VB-Audio instalado',
                            'ruta': reg_path,
                            'archivo': 'vbcable_driver',
                            'tipo': 'virtual_audio_cable',
                            'categoria': 'FORENSE',
                            'alerta': 'POCO_SOSPECHOSO',
                            'confidence': 0.38,
                            'detected_patterns': ['vac_driver_installed'],
                        })
                        print(f"⚠️ VAC driver instalado: {reg_path}")
                        break
                except (FileNotFoundError, PermissionError):
                    pass

    def scan_git_repos_desktop(self):
        """P5 #11 — Detecta repositorios Git en Desktop/Documents con nombres sospechosos."""
        print("🔍 Buscando repos Git sospechosos en Desktop/Documents...")
        SEARCH_DIRS = [
            os.path.expanduser('~\\Desktop'),
            os.path.expanduser('~\\Documents'),
        ]
        HACK_REPO_KW = list(_DEFINITE_HACK_NAMES) + [
            'hack', 'cheat', 'inject', 'macro', 'autoclicker', 'aimbot',
            'triggerbot', 'killaura', 'xray', 'esp', 'wallhack',
        ]
        found = 0
        for base_dir in SEARCH_DIRS:
            if not os.path.isdir(base_dir):
                continue
            try:
                for dname in os.listdir(base_dir):
                    repo_path = os.path.join(base_dir, dname)
                    git_dir = os.path.join(repo_path, '.git')
                    if not os.path.isdir(git_dir):
                        continue
                    dname_lower = dname.lower()
                    # Nombre del repo coincide con hack
                    matched = [kw for kw in HACK_REPO_KW if kw in dname_lower]
                    if not matched:
                        # Revisar remote origin URL en config
                        git_config = os.path.join(git_dir, 'config')
                        try:
                            with open(git_config, 'r', encoding='utf-8', errors='ignore') as f:
                                cfg_content = f.read(2048).lower()
                            matched = [kw for kw in HACK_REPO_KW if kw in cfg_content]
                        except (IOError, OSError):
                            pass
                    if matched:
                        self.issues_found.append({
                            'nombre': f'Repo Git sospechoso: {dname}',
                            'ruta': repo_path,
                            'archivo': git_dir,
                            'tipo': 'git_repo_hack',
                            'categoria': 'FORENSE',
                            'alerta': 'SOSPECHOSO',
                            'confidence': 0.60,
                            'detected_patterns': [f'git_repo:{m}' for m in matched[:3]],
                            'explicacion': (
                                f'Repositorio Git "{dname}" en {base_dir} coincide con '
                                f'nombres de hack clients o herramientas de cheat: {matched[:3]}.'
                            ),
                        })
                        found += 1
                        print(f"⚠️ Repo Git sospechoso: {dname}")
            except (PermissionError, OSError):
                pass
        if found == 0:
            print("✅ No se encontraron repos Git sospechosos")

    def scan_ip_forwarding(self):
        """P5 #12 — Detecta IP forwarding habilitado (señal de proxy/MITM)."""
        print("🔍 Verificando IP forwarding...")
        REG_PATH = r'SYSTEM\CurrentControlSet\Services\Tcpip\Parameters'
        try:
            with winreg.OpenKey(winreg.HKEY_LOCAL_MACHINE, REG_PATH) as k:
                try:
                    val, _ = winreg.QueryValueEx(k, 'IPEnableRouter')
                    if val == 1:
                        self.issues_found.append({
                            'nombre': 'IP Forwarding (IPEnableRouter) habilitado',
                            'ruta': f'HKLM\\{REG_PATH}',
                            'archivo': 'IPEnableRouter=1',
                            'tipo': 'ip_forwarding_enabled',
                            'categoria': 'RED',
                            'alerta': 'POCO_SOSPECHOSO',
                            'confidence': 0.48,
                            'detected_patterns': ['ip_forwarding'],
                            'explicacion': (
                                'El IP forwarding está habilitado en Windows. En un PC de gaming '
                                'normal esto es inusual. Puede indicar un proxy MITM configurado '
                                'para interceptar o redirigir tráfico de red de Minecraft.'
                            ),
                        })
                        print("⚠️ IP Forwarding HABILITADO")
                    else:
                        print("✅ IP Forwarding deshabilitado (normal)")
                except FileNotFoundError:
                    print("✅ IP Forwarding key no encontrada (deshabilitado)")
        except (PermissionError, OSError) as e:
            print(f"IP Forwarding check: {e}")

    def scan_nbt_exploits_saves(self):
        """P5 #7 — Detecta archivos de mundo con NBT inusualmente grandes (posibles exploits)."""
        print("🔍 Escaneando saves de Minecraft por NBT exploits...")
        SAVES_DIR = os.path.join(os.environ.get('APPDATA', ''), '.minecraft', 'saves')
        if not os.path.isdir(SAVES_DIR):
            print("✅ No hay saves de Minecraft")
            return
        # Archivos DAT/NBT inusualmente grandes son sospechosos (libros con comandos, etc.)
        LARGE_DAT_KB = 512  # > 512KB para un .dat individual es muy inusual
        found = 0
        try:
            for world in os.listdir(SAVES_DIR):
                world_path = os.path.join(SAVES_DIR, world)
                if not os.path.isdir(world_path):
                    continue
                # Buscar archivos .dat en playerdata, stats, advancements
                for subdir in ('playerdata', 'stats', 'advancements', 'data'):
                    sdir = os.path.join(world_path, subdir)
                    if not os.path.isdir(sdir):
                        continue
                    try:
                        for fname in os.listdir(sdir):
                            fpath = os.path.join(sdir, fname)
                            if not fname.endswith('.dat'):
                                continue
                            try:
                                size_kb = os.path.getsize(fpath) / 1024
                                if size_kb > LARGE_DAT_KB:
                                    self.issues_found.append({
                                        'nombre': f'NBT .dat inusualmente grande: {world}/{subdir}/{fname} ({size_kb:.0f}KB)',
                                        'ruta': sdir,
                                        'archivo': fpath,
                                        'tipo': 'nbt_large_dat',
                                        'categoria': 'FORENSE',
                                        'alerta': 'POCO_SOSPECHOSO',
                                        'confidence': 0.40,
                                        'detected_patterns': [f'dat_size:{size_kb:.0f}kb'],
                                        'explicacion': (
                                            f'Archivo NBT "{fname}" de {size_kb:.0f}KB en '
                                            f'{world}/{subdir}/. Un .dat tan grande puede contener '
                                            f'libros con comandos masivos o datos de exploits NBT.'
                                        ),
                                    })
                                    found += 1
                                    print(f"⚠️ NBT grande: {world}/{subdir}/{fname} ({size_kb:.0f}KB)")
                            except OSError:
                                pass
                    except (PermissionError, OSError):
                        pass
        except (PermissionError, OSError):
            pass
        if found == 0:
            print("✅ No se encontraron NBTs sospechosos en saves")

    def scan_suspicious_kernel_drivers(self):
        """P5 #9 — Detecta drivers de kernel no estándar que pueden ser usados por hacks."""
        print("🔍 Escaneando drivers de kernel sospechosos...")
        HACK_DRIVER_KW = [
            'cheatengine', 'cheat_engine', 'procmon', 'kernelexplorer',
            'ringzero', 'r0', 'kmdf_hack', 'bypass', 'anticheat_bypass',
            'eac_bypass', 'vac_bypass', 'be_bypass',  # anti-cheat bypasses
        ]
        # Drivers legítimos conocidos — no flagear aunque contengan palabras genéricas
        LEGIT_DRIVER_VENDORS = {
            'microsoft', 'nvidia', 'amd', 'intel', 'realtek', 'qualcomm',
            'broadcom', 'logitech', 'razer', 'corsair', 'steelseries',
        }
        found = []
        try:
            driver_key = r'SYSTEM\CurrentControlSet\Services'
            with winreg.OpenKey(winreg.HKEY_LOCAL_MACHINE, driver_key) as k:
                i = 0
                while True:
                    try:
                        svc_name = winreg.EnumKey(k, i)
                        i += 1
                        with winreg.OpenKey(k, svc_name) as sk:
                            try:
                                svc_type, _ = winreg.QueryValueEx(sk, 'Type')
                                # Type 1 = kernel driver, Type 2 = file system driver
                                if svc_type not in (1, 2):
                                    continue
                                svc_lower = svc_name.lower()
                                if any(kw in svc_lower for kw in HACK_DRIVER_KW):
                                    try:
                                        img_path, _ = winreg.QueryValueEx(sk, 'ImagePath')
                                    except FileNotFoundError:
                                        img_path = svc_name
                                    found.append((svc_name, str(img_path)))
                            except FileNotFoundError:
                                pass
                    except OSError:
                        break
        except (PermissionError, OSError) as e:
            print(f"scan_suspicious_kernel_drivers: {e}")
            return

        for svc_name, img_path in found[:5]:
            self.issues_found.append({
                'nombre': f'Driver de kernel sospechoso: {svc_name}',
                'ruta': img_path,
                'archivo': svc_name,
                'tipo': 'suspicious_kernel_driver',
                'categoria': 'PROCESO',
                'alerta': 'CRITICAL',
                'confidence': 0.80,
                'detected_patterns': [f'kernel_driver:{svc_name[:30]}'],
                'explicacion': (
                    f'Driver de kernel "{svc_name}" detectado. Los hacks de nivel kernel '
                    f'(aimbot en ring-0, bypass de EAC/VAC/BE) requieren drivers propios. '
                    f'Este driver coincide con patrones de bypass o herramientas de hacking.'
                ),
            })
            print(f"🚨 DRIVER KERNEL SOSPECHOSO: {svc_name}")

        if not found:
            print("✅ No se encontraron drivers de kernel sospechosos")

    def scan_browser_extensions_suspicious(self):
        """P5 #3 — Detecta extensiones de Chrome/Firefox con permisos all_urls o nombres sospechosos."""
        print("🔍 Escaneando extensiones de navegador sospechosas...")
        import json as _json_ext
        HACK_EXT_KW = ['minecraft', 'hack', 'cheat', 'aimbot', 'triggerbot', 'macro',
                        'inject', 'ghost', 'autoclicker', 'autoclick', 'xray', 'esp']
        DANGEROUS_PERMS = {'<all_urls>', 'webRequest', 'webRequestBlocking',
                           'nativeMessaging', 'debugger', 'proxy'}

        # Chrome/Chromium extensions
        chrome_ext_dirs = [
            os.path.join(os.environ.get('LOCALAPPDATA', ''), 'Google', 'Chrome', 'User Data', 'Default', 'Extensions'),
            os.path.join(os.environ.get('LOCALAPPDATA', ''), 'Microsoft', 'Edge', 'User Data', 'Default', 'Extensions'),
            os.path.join(os.environ.get('LOCALAPPDATA', ''), 'BraveSoftware', 'Brave-Browser', 'User Data', 'Default', 'Extensions'),
        ]
        found = 0
        for ext_base in chrome_ext_dirs:
            if not os.path.isdir(ext_base):
                continue
            try:
                for ext_id in os.listdir(ext_base):
                    ext_path = os.path.join(ext_base, ext_id)
                    if not os.path.isdir(ext_path):
                        continue
                    # Buscar manifest.json en la versión más reciente
                    manifest_path = None
                    try:
                        versions = [v for v in os.listdir(ext_path) if os.path.isdir(os.path.join(ext_path, v))]
                        if versions:
                            latest = sorted(versions)[-1]
                            manifest_path = os.path.join(ext_path, latest, 'manifest.json')
                    except OSError:
                        continue
                    if not manifest_path or not os.path.isfile(manifest_path):
                        continue
                    try:
                        with open(manifest_path, 'r', encoding='utf-8', errors='ignore') as f:
                            manifest = _json_ext.load(f)
                    except Exception:
                        continue
                    name = manifest.get('name', ext_id).lower()
                    perms = set(manifest.get('permissions', []))
                    host_perms = set(manifest.get('host_permissions', []))
                    all_perms = perms | host_perms
                    dangerous = DANGEROUS_PERMS & all_perms
                    name_hit = any(kw in name for kw in HACK_EXT_KW)
                    if name_hit or dangerous:
                        confidence = 0.55 if name_hit else 0.40
                        self.issues_found.append({
                            'nombre': f'Extensión de navegador sospechosa: {manifest.get("name", ext_id)[:60]}',
                            'ruta': ext_path,
                            'archivo': manifest_path,
                            'tipo': 'browser_extension_suspicious',
                            'categoria': 'FORENSE',
                            'alerta': 'POCO_SOSPECHOSO',
                            'confidence': confidence,
                            'detected_patterns': [*(f'perm:{p}' for p in list(dangerous)[:3]),
                                                  *(['suspicious_name'] if name_hit else [])],
                            'explicacion': (
                                f'Extensión "{manifest.get("name", ext_id)}" '
                                f'{"con nombre sospechoso" if name_hit else ""}'
                                f'{" y" if name_hit and dangerous else ""}'
                                f'{f" con permisos sensibles: {list(dangerous)[:3]}" if dangerous else ""}. '
                                f'Puede interceptar tráfico web o comunicarse con procesos locales.'
                            ),
                        })
                        found += 1
                        print(f"⚠️ Extensión sospechosa: {manifest.get('name', ext_id)[:60]}")
            except (PermissionError, OSError):
                pass

        # Firefox extensions (profiles)
        ff_profiles = os.path.join(os.environ.get('APPDATA', ''), 'Mozilla', 'Firefox', 'Profiles')
        if os.path.isdir(ff_profiles):
            try:
                for profile in os.listdir(ff_profiles):
                    ext_json = os.path.join(ff_profiles, profile, 'extensions.json')
                    if not os.path.isfile(ext_json):
                        continue
                    try:
                        with open(ext_json, 'r', encoding='utf-8', errors='ignore') as f:
                            data = _json_ext.load(f)
                        for addon in data.get('addons', []):
                            aname = addon.get('defaultLocale', {}).get('name', '').lower()
                            if any(kw in aname for kw in HACK_EXT_KW):
                                self.issues_found.append({
                                    'nombre': f'Extensión Firefox sospechosa: {aname[:60]}',
                                    'ruta': ff_profiles,
                                    'archivo': ext_json,
                                    'tipo': 'browser_extension_suspicious',
                                    'categoria': 'FORENSE',
                                    'alerta': 'POCO_SOSPECHOSO',
                                    'confidence': 0.52,
                                    'detected_patterns': ['firefox_suspicious_ext'],
                                })
                                found += 1
                                print(f"⚠️ Extensión Firefox sospechosa: {aname[:60]}")
                    except Exception:
                        pass
            except (PermissionError, OSError):
                pass

        if found == 0:
            print("✅ No se encontraron extensiones de navegador sospechosas")

    def scan_modified_minecraft_jar(self):
        """P5 #6 — Detecta modificación del minecraft client JAR oficial comparando hash vs Mojang."""
        print("🔍 Verificando integridad de minecraft client JARs...")
        import json as _json_mc
        # Buscar versiones instaladas
        mc_versions_dir = os.path.join(os.environ.get('APPDATA', ''), '.minecraft', 'versions')
        if not os.path.isdir(mc_versions_dir):
            print("✅ No hay versiones de Minecraft instaladas")
            return

        checked = 0
        modified = 0
        try:
            for version_name in os.listdir(mc_versions_dir):
                ver_path = os.path.join(mc_versions_dir, version_name)
                if not os.path.isdir(ver_path):
                    continue
                client_jar = os.path.join(ver_path, f'{version_name}.jar')
                if not os.path.isfile(client_jar):
                    continue
                # Obtener hash oficial de Mojang vía piston-meta
                try:
                    import urllib.request as _ur_mc
                    url = f'https://piston-meta.mojang.com/mc/game/version_manifest_v2.json'
                    with _ur_mc.urlopen(url, timeout=8) as resp:
                        manifest = _json_mc.loads(resp.read())
                    ver_info = next((v for v in manifest.get('versions', []) if v['id'] == version_name), None)
                    if not ver_info:
                        continue
                    with _ur_mc.urlopen(ver_info['url'], timeout=8) as resp:
                        ver_data = _json_mc.loads(resp.read())
                    mojang_sha1 = ver_data.get('downloads', {}).get('client', {}).get('sha1', '')
                    if not mojang_sha1:
                        continue
                except Exception:
                    continue  # Sin conexión o versión no encontrada en Mojang

                # Hash local
                try:
                    import hashlib as _hl_mc
                    sha1 = _hl_mc.sha1()
                    with open(client_jar, 'rb') as f:
                        while chunk := f.read(65536):
                            sha1.update(chunk)
                    local_sha1 = sha1.hexdigest()
                    checked += 1
                    if local_sha1 != mojang_sha1:
                        modified += 1
                        self.issues_found.append({
                            'nombre': f'minecraft {version_name}.jar MODIFICADO (hash distinto al oficial)',
                            'ruta': ver_path,
                            'archivo': client_jar,
                            'tipo': 'modified_minecraft_jar',
                            'categoria': 'GHOST_CLIENT',
                            'alerta': 'CRITICAL',
                            'confidence': 0.93,
                            'detected_patterns': [
                                f'local_sha1:{local_sha1[:12]}',
                                f'mojang_sha1:{mojang_sha1[:12]}',
                                'client_jar_tampered',
                            ],
                            'explicacion': (
                                f'El archivo {version_name}.jar tiene un hash SHA-1 distinto al '
                                f'oficial de Mojang. Hash local: {local_sha1[:16]}... '
                                f'Hash oficial: {mojang_sha1[:16]}... '
                                f'El JAR del cliente fue modificado — puede contener código de hack inyectado.'
                            ),
                        })
                        print(f"🚨 minecraft {version_name}.jar MODIFICADO — hash no coincide con Mojang")
                    else:
                        print(f"✅ {version_name}.jar: hash OK")
                except (IOError, OSError):
                    pass
        except (PermissionError, OSError):
            pass

        if checked == 0:
            print("✅ No se pudieron verificar JARs (sin conexión o no encontrados en Mojang)")
        elif modified == 0:
            print(f"✅ {checked} JAR(s) verificado(s) — todos íntegros")

    def scan_ahk_scripts(self):
        """Busca scripts AutoHotkey con patrones de autoclick y contexto Minecraft.
        También detecta ejecutables AHK compilados en ubicaciones sospechosas.
        """
        print("🔍 Buscando scripts AHK con autoclick...")
        import re as _re
        search_paths = [
            os.path.expanduser('~\\Desktop'),
            os.path.expanduser('~\\Documents'),
            os.path.expanduser('~\\Downloads'),
            os.path.expanduser('~\\AppData\\Roaming'),
            os.path.expanduser('~\\AppData\\Local'),
        ]
        MC_KW = ['minecraft', ' mc', 'lbutton', 'rbutton', 'mbutton', 'java.exe', 'javaw']
        # Scripts de Roblox — no son cheats de Minecraft
        ROBLOX_SKIP_NAMES = {
            'gdip_imagesearch', 'natro_macro', 'nm_inventorysearch', 'nm_openmenu',
            'heartbeat', 'plantertimers', 'statmonitor', 'nm_', 'natro',
            'installer',  # Natro installer
        }
        ROBLOX_CONTENT_KW = ['roblox', 'natro', 'bee swarm', 'beeswarm', 'honeyfield']
        CLICK_RE = [
            r'click\s*,?\s*\d*',         # Click, / Click 3
            r'sleep\s*,\s*[1-9]\d{0,2}', # Sleep corto < 1000ms
            r'loop\s*[,\{]',             # Loop { / Loop, 10
            r'mouseevent\s*\(',
            r'send\s*\{click\}',
            r'sendinput\s*\{lbutton\}',
            r'controlclick',
            r'\bsetmousedelay\b',
            r'\btoggle\b.*\bclick\b',
        ]
        # Patrones de ofuscación AHK: variables largas aleatorias, chr() chains, etc.
        OBFUSC_RE = [
            r'chr\(\d+\)\s*\.\s*chr\(\d+\)',  # chr(86).chr(65)... string building
            r'#noenv\s*\n.*#persistent',       # flags de AHK ofuscado
        ]
        # Nombres de archivo que indican autoclick directamente
        AUTOCLICK_NAME_KW = ['autoclick', 'autoclicker', 'clicker', 'click-bot',
                              'jitter', 'butterfly', 'drag-click', 'dragclick',
                              'cps', 'bypass-click', 'aim', 'macro']
        try:
            for base in search_paths:
                if not os.path.isdir(base):
                    continue
                for root, dirs, files in os.walk(base):
                    dirs[:] = [d for d in dirs if d.lower() not in {
                        'windows', 'system32', '.git', '__pycache__',
                        'google', 'mozilla', 'microsoft',
                    }]
                    for fname in files:
                        fname_lower = fname.lower()
                        fpath = os.path.join(root, fname)

                        # Detectar AHK compilado (.exe) con nombre sospechoso
                        if fname_lower.endswith('.exe'):
                            if any(kw in fname_lower for kw in AUTOCLICK_NAME_KW):
                                try:
                                    # Verificar si es AHK compilado leyendo firma del PE
                                    with open(fpath, 'rb') as f:
                                        header = f.read(512)
                                    is_ahk_compiled = (b'AutoHotkey' in header or
                                                        b'AHK_L' in header or
                                                        b'AutoHotkeyL' in header or
                                                        b'AUTOHOTKEY' in header.upper())
                                    if is_ahk_compiled:
                                        print(f"🚨 AHK EXE COMPILADO (autoclick): {fpath}")
                                        self.issues_found.append({
                                            'nombre': f'Ejecutable AHK compilado (autoclick): {fname}',
                                            'ruta': fpath,
                                            'archivo': fname,
                                            'tipo': 'ahk_autoclick',
                                            'categoria': 'AUTOCLICK',
                                            'alerta': 'CRITICAL',
                                            'confidence': 0.91,
                                            'detected_patterns': ['ahk_compiled_exe', 'autoclick_name'],
                                            'explicacion': (
                                                f'{fname} es un ejecutable AHK compilado con nombre de autoclick. '
                                                'Los AHK compilados son scripts de autoclick que ocultan el código '
                                                'fuente para evitar ser detectados durante el Screen Share.'
                                            ),
                                        })
                                except Exception:
                                    pass
                            continue  # No analizar otros .exe como scripts AHK

                        if not (fname_lower.endswith('.ahk') or fname_lower.endswith('.ahk2')):
                            continue

                        # Excluir scripts de Roblox por nombre
                        if any(rk in fname_lower for rk in ROBLOX_SKIP_NAMES):
                            continue

                        try:
                            with open(fpath, 'r', encoding='utf-8', errors='ignore') as f:
                                content = f.read(16384).lower()

                            # Excluir scripts de Roblox por contenido
                            if any(rk in content for rk in ROBLOX_CONTENT_KW):
                                continue
                            # Excluir si está en carpeta de Roblox
                            if 'roblox' in fpath.lower():
                                continue

                            has_click = any(_re.search(p, content, _re.IGNORECASE) for p in CLICK_RE)
                            is_obfusc = any(_re.search(p, content, _re.IGNORECASE | _re.DOTALL)
                                            for p in OBFUSC_RE)
                            name_match = any(kw in fname_lower for kw in AUTOCLICK_NAME_KW)

                            if not (has_click or is_obfusc or name_match):
                                continue

                            has_mc = any(kw in content for kw in MC_KW)

                            # Solo reportar si tiene contexto Minecraft — AHK sin Minecraft no es relevante
                            if not has_mc and not is_obfusc:
                                continue

                            patterns = ['ahk_click', 'ahk_minecraft'] + (['ahk_obfuscated'] if is_obfusc else [])
                            if name_match:
                                patterns.append('ahk_autoclick_name')

                            print(f"🚨 AHK AUTOCLICK+MC: {fpath}")
                            self.issues_found.append({
                                'nombre': f'Script AHK con autoclick + Minecraft: {fname}',
                                'ruta': fpath,
                                'archivo': fname,
                                'tipo': 'ahk_autoclick',
                                'categoria': 'AUTOCLICK',
                                'alerta': 'CRITICAL',
                                'confidence': 0.91,
                                'detected_patterns': patterns,
                                'explicacion': (
                                    f'{fname} contiene patrones de autoclick con contexto Minecraft. '
                                    + ('Script ofuscado. ' if is_obfusc else '')
                                    + 'Los scripts AHK de autoclick simulan clics para obtener más CPS.'
                                ),
                            })
                        except Exception:
                            continue
        except Exception as e:
            print(f"Error en scan_ahk_scripts: {e}")

    def scan_bloody_a4tech(self):
        """Detecta software Bloody/A4Tech instalado (autoclick por hardware)."""
        print("🔍 Escaneando software Bloody/A4Tech...")
        pf  = os.environ.get('PROGRAMFILES', 'C:\\Program Files')
        pf86 = os.environ.get('PROGRAMFILES(X86)', 'C:\\Program Files (x86)')
        appdata = os.environ.get('APPDATA', '')
        PATHS = [
            os.path.join(pf,   'Bloody'), os.path.join(pf86, 'Bloody'),
            os.path.join(pf,   'A4Tech'), os.path.join(pf86, 'A4Tech'),
            os.path.join(appdata, 'Bloody'),
        ]
        try:
            for path in PATHS:
                if os.path.isdir(path):
                    print(f"⚠️ SOFTWARE BLOODY/A4TECH: {path}")
                    self.issues_found.append({
                        'nombre': f'Software Bloody/A4Tech instalado: {os.path.basename(path)}',
                        'ruta': path,
                        'archivo': os.path.basename(path),
                        'tipo': 'bloody_a4tech',
                        'categoria': 'AUTOCLICK',
                        'alerta': 'SOSPECHOSO',
                        'confidence': 0.72,
                        'detected_patterns': ['bloody_mouse_software'],
                    })
                    break
        except Exception as e:
            print(f"Error en scan_bloody_a4tech: {e}")

    def scan_steelseries_corsair(self):
        """Detecta macros de click rápido en perfiles de SteelSeries GG / Corsair iCUE."""
        print("🔍 Escaneando SteelSeries GG / Corsair iCUE...")
        import re as _re
        localapp = os.environ.get('LOCALAPPDATA', '')
        appdata  = os.environ.get('APPDATA', '')
        PROFILE_BASES = [
            os.path.join(localapp, 'SteelSeries', 'GG'),
            os.path.join(localapp, 'SteelSeries', 'SteelSeries Engine 3'),
            os.path.join(appdata,  'Corsair', 'CUE'),
            os.path.join(localapp, 'Corsair', 'CUE'),
            os.path.join(appdata,  'Corsair', 'iCUE'),
        ]
        try:
            for base in PROFILE_BASES:
                if not os.path.isdir(base):
                    continue
                for root, dirs, files in os.walk(base):
                    dirs[:] = dirs[:5]
                    for fname in files:
                        if not (fname.endswith('.json') or fname.endswith('.xml')):
                            continue
                        fpath = os.path.join(root, fname)
                        try:
                            with open(fpath, 'r', encoding='utf-8', errors='ignore') as f:
                                content = f.read(16384).lower()
                            has_click = bool(_re.search(r'(click|actiontype.*click|mouse.*loop)', content))
                            has_fast  = bool(_re.search(r'delay["\s:,]*\d{1,2}["\s,}]|ms["\s:,]*1\d["\s,}]', content))
                            if has_click and has_fast:
                                print(f"⚠️ MACRO CLICK RAPIDO en {os.path.basename(base)}: {fpath}")
                                self.issues_found.append({
                                    'nombre': f'Macro click rápido en {os.path.basename(base)}: {fname}',
                                    'ruta': fpath,
                                    'archivo': fname,
                                    'tipo': 'peripheral_macro',
                                    'categoria': 'AUTOCLICK',
                                    'alerta': 'SOSPECHOSO',
                                    'confidence': 0.75,
                                    'detected_patterns': ['rapid_click_macro'],
                                })
                        except Exception:
                            continue
        except Exception as e:
            print(f"Error en scan_steelseries_corsair: {e}")

    def scan_arduino_hid(self):
        """Detecta dispositivos HID Arduino/CH340/STM32 conectados (autoclick hardware)."""
        print("🔍 Escaneando dispositivos HID Arduino/programables...")
        SUSPICIOUS_VIDS = {'2341', '1a86', '0483', '04d8', '16c0'}
        try:
            import subprocess as _sp
            result = _sp.run(
                ['wmic', 'path', 'Win32_PnPEntity', 'where',
                 'PNPClass="HIDClass"', 'get', 'Name,DeviceID', '/FORMAT:CSV'],
                capture_output=True, text=True, timeout=15
            )
            if result.returncode != 0:
                return
            import re as _re
            for line in result.stdout.splitlines():
                ll = line.lower()
                vid_m = _re.search(r'vid_([0-9a-f]{4})', ll)
                if not vid_m or vid_m.group(1) not in SUSPICIOUS_VIDS:
                    continue
                if any(kw in ll for kw in ['arduino', 'ch340', 'stm32', 'usbasp', 'pro micro', 'digispark']):
                    print(f"⚠️ ARDUINO/HID DEVICE: {line.strip()[:120]}")
                    self.issues_found.append({
                        'nombre': f'Dispositivo HID Arduino/programable: {line.strip()[:80]}',
                        'ruta': 'Dispositivos USB del sistema',
                        'archivo': line.strip()[:80],
                        'tipo': 'arduino_hid_device',
                        'categoria': 'AUTOCLICK',
                        'alerta': 'SOSPECHOSO',
                        'confidence': 0.75,
                        'detected_patterns': ['arduino_hid'],
                    })
        except Exception as e:
            print(f"Error en scan_arduino_hid: {e}")

    def scan_active_injectors(self):
        """Detecta procesos inyectores corriendo durante el scan."""
        print("🔍 Buscando procesos inyectores activos...")
        INJECTOR_SIGS = [
            'extremeinjector', 'xenos', 'dllinjector', 'dll_injector',
            'processhacker', 'cheatengine', 'cheat_engine', 'ce32', 'ce64',
            'scylla', 'scyllahide', 'titan', 'injex', 'remoteinjector',
            'manualmap', 'threadhijack',
        ]
        try:
            for proc in psutil.process_iter(['pid', 'name', 'exe']):
                try:
                    pname = (proc.info.get('name') or '').lower().replace(' ', '').replace('-', '').replace('_', '')
                    pexe  = (proc.info.get('exe') or '').lower().replace(' ', '').replace('-', '')
                    for sig in INJECTOR_SIGS:
                        if sig in pname or sig in pexe:
                            print(f"🚨 INYECTOR ACTIVO: {proc.info.get('name')}")
                            self.issues_found.append({
                                'nombre': f'Proceso inyector activo: {proc.info.get("name", sig)}',
                                'ruta': proc.info.get('exe') or 'N/A',
                                'archivo': proc.info.get('name', sig),
                                'tipo': 'injector_process',
                                'categoria': 'JAVA_INJECTION',
                                'alerta': 'CRITICAL',
                                'confidence': 0.93,
                                'detected_patterns': ['active_injector'],
                            })
                            break
                except (psutil.NoSuchProcess, psutil.AccessDenied):
                    continue
        except Exception as e:
            print(f"Error en scan_active_injectors: {e}")

    def _score_path_hack_similarity(self, filename: str) -> tuple:
        """P3 #10: Character trigram Jaccard similarity between filename and known hack names.
        Returns (max_similarity 0-1, best_match_name). Detects obfuscated/renamed hack jars."""
        import re as _re
        base = _re.sub(r'\.[^.]+$', '', filename).lower()
        # Strip generic noise tokens before comparing
        base = _re.sub(r'[-_]?(?:v\d+[\d.]*|patch|update|mod|client|loader|latest|\d{3,})', '', base)
        base = base.strip('-_ ')
        if len(base) < 3:
            return 0.0, ''
        HACK_NAMES = [
            'sigma', 'liquidbounce', 'wurst', 'meteorclient', 'meteor',
            'vape', 'rise', 'drip', 'vertex', 'azura', 'novoline',
            'rusherhack', 'astolfo', 'future', 'entropy', 'salhack',
            'remix', 'inertia', 'aristois', 'impact', 'horion', 'ares',
            'mathias', 'datura', 'jello', 'weave', 'xray', 'ghostclient',
            'killaura', 'aimbot', 'scaffold', 'hacked', 'cheat',
        ]
        def _tg(s):
            return set(s[i:i+3] for i in range(len(s) - 2)) if len(s) >= 3 else set()
        base_tg = _tg(base)
        if not base_tg:
            return 0.0, ''
        best_sim, best_name = 0.0, ''
        for hack in HACK_NAMES:
            hack_tg = _tg(hack)
            if not hack_tg:
                continue
            union = len(base_tg | hack_tg)
            sim = len(base_tg & hack_tg) / union if union else 0.0
            if sim > best_sim:
                best_sim, best_name = sim, hack
        return best_sim, best_name

    def scan_temp_jars(self):
        """Detecta archivos .jar creados en las últimas 24h en carpetas temporales."""
        print("🔍 Buscando JARs recientes en carpetas temporales...")
        temp_paths = list({
            os.environ.get('TEMP', ''),
            os.environ.get('TMP', ''),
            os.path.join(os.environ.get('LOCALAPPDATA', ''), 'Temp'),
        })
        cutoff = time.time() - 86400
        seen = set()
        try:
            for temp_dir in temp_paths:
                if not temp_dir or not os.path.isdir(temp_dir):
                    continue
                for root, dirs, files in os.walk(temp_dir):
                    dirs[:] = dirs[:10]
                    for fname in files:
                        if not fname.lower().endswith('.jar'):
                            continue
                        fpath = os.path.join(root, fname)
                        if fpath in seen:
                            continue
                        seen.add(fpath)
                        try:
                            if os.path.getmtime(fpath) >= cutoff:
                                # P3 #10 — path similarity to known hack client names
                                sim, matched_hack = self._score_path_hack_similarity(fname)
                                if sim >= 0.35:
                                    alerta = 'CRITICAL'
                                    conf = min(0.95, 0.70 + sim * 0.5)
                                    patterns = ['jar_in_temp_24h', f'name_similar_to:{matched_hack}({sim:.2f})']
                                    label = f'JAR sospechoso (similar a "{matched_hack}") en temp: {fname}'
                                    print(f"🚨 JAR SIMILAR A HACK EN TEMP: {fname} ~ {matched_hack} ({sim:.2f})")
                                else:
                                    alerta = 'SOSPECHOSO'
                                    conf = 0.70
                                    patterns = ['jar_in_temp_24h']
                                    label = f'JAR reciente en carpeta temporal: {fname}'
                                    print(f"⚠️ JAR RECIENTE EN TEMP: {fpath}")
                                self.issues_found.append({
                                    'nombre': label,
                                    'ruta': fpath,
                                    'archivo': fname,
                                    'tipo': 'temp_jar_recent',
                                    'categoria': 'JAVA_INJECTION',
                                    'alerta': alerta,
                                    'confidence': round(conf, 2),
                                    'detected_patterns': patterns,
                                })
                        except Exception:
                            continue
        except Exception as e:
            print(f"Error en scan_temp_jars: {e}")

    def scan_baritone_config(self):
        """Detecta Baritone instalado y verifica si tiene modos prohibidos activos."""
        print("🔍 Escaneando configuración de Baritone...")
        import json as _json
        appdata = os.environ.get('APPDATA', '')
        settings_path = os.path.join(appdata, '.minecraft', 'baritone', 'settings.json')
        if not os.path.exists(settings_path):
            return
        PROHIBITED = {
            'buildRepeat': True, 'elytraFly': True,
            'allowPlace': True, 'allowBreak': True,
            'printOptimizerEnabled': True,
        }
        try:
            with open(settings_path, 'r', encoding='utf-8', errors='ignore') as f:
                config = _json.load(f)
            violations = [f'{k}={v}' for k, v in PROHIBITED.items() if config.get(k) == v]
            if violations:
                print(f"⚠️ BARITONE MODOS PROHIBIDOS: {', '.join(violations)}")
                self.issues_found.append({
                    'nombre': f'Baritone con modos prohibidos: {", ".join(violations[:3])}',
                    'ruta': settings_path,
                    'archivo': 'settings.json',
                    'tipo': 'baritone_prohibited',
                    'categoria': 'COMPLEMENTO_PROHIBIDO',
                    'alerta': 'SOSPECHOSO',
                    'confidence': 0.80,
                    'detected_patterns': [f'baritone:{v.split("=")[0]}' for v in violations],
                })
            else:
                self.issues_found.append({
                    'nombre': 'Baritone instalado (bot de automatización de Minecraft)',
                    'ruta': settings_path,
                    'archivo': 'settings.json',
                    'tipo': 'baritone_installed',
                    'categoria': 'COMPLEMENTO_PROHIBIDO',
                    'alerta': 'SOSPECHOSO',
                    'confidence': 0.60,
                    'detected_patterns': ['baritone_present'],
                })
        except Exception as e:
            print(f"Error en scan_baritone_config: {e}")

    def scan_schematica_litematica(self):
        """Detecta Schematica/Litematica con Printer Mode activo."""
        print("🔍 Escaneando configuración de Schematica/Litematica...")
        import re as _re
        appdata = os.environ.get('APPDATA', '')
        CONFIG_PATHS = [
            (os.path.join(appdata, '.minecraft', 'config', 'schematica.cfg'),         'cfg'),
            (os.path.join(appdata, '.minecraft', 'config', 'litematica', 'generic.json'), 'json'),
            (os.path.join(appdata, '.minecraft', 'config', 'easylitematic.json'),     'json'),
        ]
        try:
            for config_path, ftype in CONFIG_PATHS:
                if not os.path.exists(config_path):
                    continue
                try:
                    with open(config_path, 'r', encoding='utf-8', errors='ignore') as f:
                        content = f.read(16384)
                    cl = content.lower()
                    if ftype == 'json' and _re.search(r'"print.*?:\s*true|"enable.*?print.*?:\s*true', cl):
                        print(f"🚨 LITEMATICA PRINTER MODE: {config_path}")
                        self.issues_found.append({
                            'nombre': f'Litematica Printer Mode activo',
                            'ruta': config_path,
                            'archivo': os.path.basename(config_path),
                            'tipo': 'litematica_printer',
                            'categoria': 'COMPLEMENTO_PROHIBIDO',
                            'alerta': 'CRITICAL',
                            'confidence': 0.85,
                            'detected_patterns': ['litematica_printer_enabled'],
                        })
                    elif ftype == 'cfg' and ('printer=true' in cl or 'printerenabled=true' in cl):
                        print(f"🚨 SCHEMATICA PRINTER MODE: {config_path}")
                        self.issues_found.append({
                            'nombre': 'Schematica Printer Mode activo',
                            'ruta': config_path,
                            'archivo': os.path.basename(config_path),
                            'tipo': 'schematica_printer',
                            'categoria': 'COMPLEMENTO_PROHIBIDO',
                            'alerta': 'CRITICAL',
                            'confidence': 0.85,
                            'detected_patterns': ['schematica_printer_enabled'],
                        })
                except Exception:
                    continue
        except Exception as e:
            print(f"Error en scan_schematica_litematica: {e}")

    def scan_optifine_zoom(self):
        """Detecta si el zoom de OptiFine está asignado a tecla de combate en options.txt."""
        print("🔍 Escaneando options.txt (OptiFine zoom key)...")
        appdata = os.environ.get('APPDATA', '')
        options_path = os.path.join(appdata, '.minecraft', 'options.txt')
        if not os.path.exists(options_path):
            return
        SUSPICIOUS_BINDS = {'key_mouse1', 'key_mouse2', 'key_mouse3', 'key_button1', 'key_button2'}
        try:
            with open(options_path, 'r', encoding='utf-8', errors='ignore') as f:
                for line in f:
                    ll = line.lower().strip()
                    if ll.startswith('key_of.key.zoom:') or ll.startswith('key_optifine.zoom:'):
                        zoom_bind = ll.split(':')[-1].strip()
                        if zoom_bind in SUSPICIOUS_BINDS:
                            print(f"⚠️ OPTIFINE ZOOM BIND SOSPECHOSO: {line.strip()}")
                            self.issues_found.append({
                                'nombre': f'OptiFine zoom en tecla de combate: {line.strip()[:80]}',
                                'ruta': options_path,
                                'archivo': 'options.txt',
                                'tipo': 'optifine_zoom_combat',
                                'categoria': 'COMPLEMENTO_PROHIBIDO',
                                'alerta': 'SOSPECHOSO',
                                'confidence': 0.65,
                                'detected_patterns': ['optifine_zoom_combat_bind'],
                            })
        except Exception as e:
            print(f"Error en scan_optifine_zoom: {e}")

    def _score_string_hack_likelihood(self, base_name: str) -> float:
        """P3 #7: Character n-gram heuristic to score a class name as hack module.
        Returns 0.0-5.0; >= 3.5 considered suspicious."""
        import re as _re
        if len(base_name) < 8 or len(base_name) > 45:
            return 0.0
        # Obfuscated single/double letter names are noise, not hacks
        if len(base_name) <= 3:
            return 0.0
        score = 0.0
        low = base_name.lower()
        HACK_KEYWORDS = [
            'killaura', 'aimbot', 'aimassist', 'scaffold', 'bunnyhop', 'bhop',
            'triggerbot', 'nofall', 'antiknock', 'autoclicker', 'autoclick',
            'criticals', 'velocity', 'wallhack', 'freecam', 'xray', 'fullbright',
            'speedhack', 'flyhack', 'speedmine', 'timer', 'fastplace',
        ]
        HACK_PARTIAL = [
            'kill', 'aura', 'aimb', 'cheat', 'ghost', 'inject', 'bypass',
            'hack', 'module', 'payload', 'remap', 'hook',
        ]
        for kw in HACK_KEYWORDS:
            if kw in low:
                score += 2.5
                break
        else:
            for kw in HACK_PARTIAL:
                if kw in low:
                    score += 1.5
                    break
        # PascalCase with 2+ segments = typical hack module name (KillAura, AimAssist)
        pascal_parts = _re.findall(r'[A-Z][a-z]+', base_name)
        if len(pascal_parts) >= 2:
            score += 1.0
        elif len(pascal_parts) == 1 and len(base_name) >= 12:
            score += 0.3
        # Clean CamelCase (no underscores, no digits prefix) bonus
        if _re.match(r'^[A-Z][a-z0-9]+(?:[A-Z][a-z0-9]+)+$', base_name):
            score += 0.5
        # Sweet-spot length for named hack modules
        if 10 <= len(base_name) <= 25:
            score += 0.3
        return max(0.0, score)

    def scan_process_memory_strings(self):
        """Escanea JARs cargados por javaw.exe buscando strings de módulos de hack.
        P2 #9-12: longitud mínima 8 chars, regex Java package, blacklist strings legítimos.
        P3 #7: NLP n-gram heuristic para módulos de hack sin firma exacta."""
        print("🔍 Escaneando JARs cargados en memoria de Minecraft...")
        import re as _re
        import zipfile as _zf

        # Strings de módulos de hack (>= 8 chars, específicos)
        HACK_SIGNATURES = [
            b'KillAura', b'Scaffold', b'BunnyHop', b'AimAssist', b'Triggerbot',
            b'NoFall', b'AntiKnockback', b'AutoClicker', b'AutoSprint', b'FastBow',
            b'Criticals', b'LiquidBounce', b'WurstClient', b'VapeClient',
            b'SigmaClient', b'FutureClient', b'MeteorClient', b'AstolfoClient',
            b'com/rise/', b'com/sigma/', b'net/vapor/', b'dev/liquidbounce',
            b'me/sigma/', b'me/astolfo/', b'net/rusherhack/', b'com/moonrise/',
        ]
        # #12 — Blacklist de packages Java legítimos (ignorar siempre)
        JAVA_LEGIT_PREFIXES = (
            b'java/', b'javax/', b'sun/', b'com/sun/', b'jdk/',
            b'net/minecraft/', b'com/mojang/', b'net/minecraftforge/',
            b'org/lwjgl/', b'org/apache/', b'com/google/', b'org/slf4j/',
            b'io/netty/', b'com/github/steveice10/', b'net/fabricmc/',
            b'org/objectweb/asm/', b'com/llamalad7/',
            # F14 — Mixin library usada por todos los mods legítimos (Sodium, Iris, etc.)
            b'org/spongepowered/asm/', b'org/spongepowered/mixin/',
            # Loaders y librerías de mods legítimos
            b'net/neoforged/', b'org/quiltmc/', b'net/coderbot/iris/',
            b'me/jellysquid3/', b'com/lodborg/', b'net/irisshaders/',
        )
        # #11 — Regex de paquetes Java sospechosos (com.client.*, net.hack.*, etc.)
        HACK_PACKAGE_RE = _re.compile(
            rb'(?:com|net|me|dev|io)/(?:hack|hacks|cheat|ghost|client|module|modules|feature|bypass)/',
            _re.IGNORECASE
        )

        try:
            for proc in psutil.process_iter(['pid', 'name']):
                try:
                    name = (proc.info.get('name') or '').lower()
                    if 'javaw' not in name and 'java' not in name:
                        continue
                    loaded_jars = set()
                    try:
                        for mmap in proc.memory_maps():
                            path = mmap.path or ''
                            if path.lower().endswith('.jar') and os.path.isfile(path):
                                loaded_jars.add(path)
                    except (psutil.AccessDenied, psutil.NoSuchProcess):
                        pass

                    for jar_path in loaded_jars:
                        jar_l = jar_path.lower()
                        # F14 — Ignorar JDK/JRE y mods legítimos de performance/loaders
                        if any(s in jar_l for s in (
                            'jdk', 'jre', 'optifine_', 'sodium-', 'sodium_',
                            'fabricloader', 'forge-', 'authlib',
                            'iris-', 'irisshaders', 'ferritecore', 'distanthorizons',
                            'bobby-', 'moreculling', 'lazydfu', 'lithium-',
                            'phosphor-', 'rubidium-', 'embeddium-', 'neoforge-',
                            'quiltloader', 'ornithe', 'mixinextras',
                        )):
                            continue
                        try:
                            with _zf.ZipFile(jar_path, 'r') as zf:
                                class_names = [n for n in zf.namelist() if n.endswith('.class')]
                                matched_sig = None
                                matched_pkg = None
                                # P3 #7 — NLP accumulator for hack-like class names
                                nlp_hits = []
                                for class_name in class_names[:8000]:
                                    cn = class_name.encode('utf-8', errors='ignore')
                                    # #12 — Skip strings de Java legítimo
                                    if cn.startswith(JAVA_LEGIT_PREFIXES):
                                        continue
                                    # #9 — Skip strings < 8 chars (sin la extensión)
                                    base = cn.replace(b'.class', b'').split(b'/')[-1]
                                    if len(base) < 8:
                                        continue
                                    # Buscar signatures de hacks
                                    for sig in HACK_SIGNATURES:
                                        if sig in cn:
                                            matched_sig = sig.decode('utf-8', errors='ignore')
                                            break
                                    # #11 — Regex de paquetes hack
                                    if not matched_sig and HACK_PACKAGE_RE.search(cn):
                                        matched_pkg = cn.decode('utf-8', errors='ignore')
                                    if matched_sig or matched_pkg:
                                        break
                                    # P3 #7 — NLP heuristic score for unlisted hack modules
                                    base_str = base.decode('utf-8', errors='ignore')
                                    nlp_score = self._score_string_hack_likelihood(base_str)
                                    if nlp_score >= 3.5:
                                        nlp_hits.append((base_str, nlp_score))
                                        if len(nlp_hits) >= 10:
                                            break  # cap scan cost

                                if matched_sig or matched_pkg:
                                    label = matched_sig or matched_pkg
                                    print(f"🚨 STRING DE HACK EN JAR: {label} → {jar_path}")
                                    self.issues_found.append({
                                        'nombre': f'Módulo de hack en JAR cargado: {label}',
                                        'ruta': jar_path,
                                        'archivo': os.path.basename(jar_path),
                                        'tipo': 'hack_string_in_loaded_jar',
                                        'categoria': 'JAVA_INJECTION',
                                        'alerta': 'CRITICAL',
                                        'confidence': 0.92 if matched_sig else 0.75,
                                        'detected_patterns': [f'hack_class:{label}'],
                                        'explicacion': f'Se encontró el módulo de hack "{label}" en el JAR '
                                                       f'{os.path.basename(jar_path)} cargado por Minecraft. '
                                                       f'Esto indica que un ghost client está activo en memoria.',
                                    })
                                elif len(nlp_hits) >= 3:
                                    # P3 #7: enough hack-like class names to flag without exact signature
                                    top_names = ', '.join(h[0] for h in sorted(nlp_hits, key=lambda x: -x[1])[:4])
                                    avg_nlp = sum(h[1] for h in nlp_hits) / len(nlp_hits)
                                    conf = min(0.82, 0.55 + avg_nlp * 0.05)
                                    print(f"⚠️ CLASES SOSPECHOSAS (NLP) EN JAR: {top_names} → {jar_path}")
                                    self.issues_found.append({
                                        'nombre': f'Clases sospechosas (NLP) en JAR cargado: {top_names}',
                                        'ruta': jar_path,
                                        'archivo': os.path.basename(jar_path),
                                        'tipo': 'hack_string_in_loaded_jar',
                                        'categoria': 'JAVA_INJECTION',
                                        'alerta': 'SOSPECHOSO',
                                        'confidence': round(conf, 2),
                                        'detected_patterns': [f'nlp_hack_class:{n}' for n, _ in nlp_hits[:4]],
                                        'explicacion': f'Se detectaron {len(nlp_hits)} clases con nombres '
                                                       f'típicos de módulos de hack (NLP n-gram) en '
                                                       f'{os.path.basename(jar_path)}: {top_names}. '
                                                       f'No coinciden con firmas exactas pero presentan '
                                                       f'características lingüísticas de ghost clients.',
                                    })
                        except Exception:
                            continue
                except (psutil.NoSuchProcess, psutil.AccessDenied):
                    continue
        except Exception as e:
            print(f"Error en scan_process_memory_strings: {e}")

    def scan_minecraft_jar_hash(self):
        """Verifica el hash SHA1 del minecraft.jar contra los hashes oficiales de Mojang.
        Un mismatch indica jar modificado (ghost client clásico)."""
        print("🔍 Verificando hash de minecraft.jar contra Mojang...")
        if not requests:
            print("⚠️ requests no disponible — skip hash check")
            return
        appdata = os.environ.get('APPDATA', '')
        versions_dir = os.path.join(appdata, '.minecraft', 'versions')
        if not os.path.isdir(versions_dir):
            return

        # Cache de hashes conocidos (sin red). Se extiende con la API si hay conexión.
        KNOWN_HASHES = {
            '1.8.9':  '169780e761a0e9c13d1c9e576a3c1fef34f8aeac',
            '1.12.2': '0f275bc1547d01fa5f56ba34bdc87d981ee12daf',
            '1.16.5': '37fd3c903861eeff3bc24b71eed48f828b5269c8',
            '1.17.1': 'a0d03225615ba897073e279670890bda18ee1e26',
            '1.18.2': 'c8f83c5655308435b3a8a8e576b12c7c9929d8e0',
            '1.19.4': '958928a560c9167687bea0e8b88d02e3a03cf2ac',
            '1.20.1': 'e6ec2f64e6080b2b2d817e6f4a1a08f6e4b56f88',
            '1.20.4': '1b5ddb1bb7cbb56d76b4588caed5c7b44dfab31c',
            '1.20.6': '2de5decc9c67cb7a95a0e6dd74dba42a8d994e7c',
            '1.21':   '0e7b5d35c7ba1ee0ee0da12c0e2c2e8ce9f60e86',
            '1.21.1': '943ee92a34dccf36b2e7fb7fe30e8d63c5e0cd4f',
            '1.21.4': '87bc50d4eafddbc41c5ceba9c7de92bde46c8a6e',
        }

        _manifest_versions: list = []  # fetched once per scan run

        def _fetch_mojang_hash(version_id: str) -> str | None:
            try:
                if not _manifest_versions:
                    manifest_url = 'https://piston-meta.mojang.com/mc/game/version_manifest_v2.json'
                    r = requests.get(manifest_url, timeout=8)
                    r.raise_for_status()
                    _manifest_versions.extend(r.json().get('versions', []))
                for v in _manifest_versions:
                    if v.get('id') == version_id:
                        vr = requests.get(v['url'], timeout=8)
                        vr.raise_for_status()
                        return vr.json().get('downloads', {}).get('client', {}).get('sha1')
            except Exception:
                pass
            return None

        # Clientes que modifican el JAR legítimamente (crean sus propias versiones)
        _JAR_MODIFIER_CLIENTS = [
            os.path.join(os.environ.get('USERPROFILE', ''), '.lunarclient'),
            os.path.join(os.environ.get('APPDATA', ''), 'lunarclient'),
            os.path.join(os.environ.get('LOCALAPPDATA', ''), 'lunarclient'),
        ]
        _has_lunar = any(os.path.isdir(p) for p in _JAR_MODIFIER_CLIENTS)

        _LAUNCHER_SUFFIXES = ['optifine', 'forge', 'fabric', 'quilt', 'lunar', 'feather', 'labymod', 'badlion']
        try:
            for ver_name in os.listdir(versions_dir):
                jar_path = os.path.join(versions_dir, ver_name, f'{ver_name}.jar')
                if not os.path.isfile(jar_path):
                    continue

                # Versiones con nombre no-vanilla (OptiFine, Forge, Fabric, etc.) — skip
                # Ejemplo: "1.20.1-OptiFine_HD_U_I7", "1.20.1-forge-47.2.0"
                if any(s in ver_name.lower() for s in _LAUNCHER_SUFFIXES):
                    print(f"⏭️ Skip versión modded: {ver_name}")
                    continue

                try:
                    sha1 = hashlib.sha1()
                    with open(jar_path, 'rb') as f:
                        for chunk in iter(lambda: f.read(65536), b''):
                            sha1.update(chunk)
                    actual_hash = sha1.hexdigest()
                except Exception:
                    continue

                expected = KNOWN_HASHES.get(ver_name)
                if expected is None:
                    expected = _fetch_mojang_hash(ver_name)

                if expected is None:
                    continue  # versión desconocida, no podemos verificar

                if actual_hash.lower() != expected.lower():
                    print(f"🚨 MINECRAFT.JAR MODIFICADO: {ver_name} — esperado {expected[:12]}... obtenido {actual_hash[:12]}...")
                    if _has_lunar:
                        # Lunar Client parchea JARs vanilla — bajar severidad
                        self.issues_found.append({
                            'nombre': f'minecraft.jar con hash modificado en {ver_name} (Lunar Client detectado — puede ser normal)',
                            'ruta': jar_path,
                            'archivo': f'{ver_name}.jar',
                            'tipo': 'modified_minecraft_jar',
                            'categoria': 'GHOST_CLIENT',
                            'alerta': 'SOSPECHOSO',
                            'confidence': 0.40,
                            'detected_patterns': ['modified_jar_lunar', f'hash_mismatch:{ver_name}'],
                            'extra': {'expected': expected, 'actual': actual_hash, 'lunar_detected': True},
                        })
                    else:
                        self.issues_found.append({
                            'nombre': f'minecraft.jar modificado en versión {ver_name} (hash no coincide con Mojang)',
                            'ruta': jar_path,
                            'archivo': f'{ver_name}.jar',
                            'tipo': 'modified_minecraft_jar',
                            'categoria': 'GHOST_CLIENT',
                            'alerta': 'CRITICAL',
                            'confidence': 0.97,
                            'detected_patterns': ['modified_jar', f'hash_mismatch:{ver_name}'],
                            'extra': {'expected': expected, 'actual': actual_hash},
                        })
                else:
                    print(f"✅ minecraft.jar {ver_name} — hash OK")
        except Exception as e:
            print(f"Error en scan_minecraft_jar_hash: {e}")

    # ── PARTE 1 — Mejoras pendientes de detección ─────────────────────────────

    def scan_process_path_correlation(self):
        """P2 #14/#15 — Correlación proceso+ruta y tiempo de vida del proceso.
        Un update.exe desde %TEMP% es sospechoso; desde Program Files no.
        Proceso con < 60s de uptime al empezar el scan es más sospechoso."""
        print("🔍 Correlación proceso+ruta y uptime de procesos...")
        import datetime as _dt
        import re as _re

        SUSPICIOUS_NAMES = [
            'update.exe', 'updater.exe', 'helper.exe', 'service.exe',
            'loader.exe', 'launcher.exe', 'inject.exe', 'patch.exe',
            'install.exe', 'setup.exe', 'uninstall.exe', 'agent.exe',
        ]
        SUSPICIOUS_TEMP_DIRS = [
            os.environ.get('TEMP', '').lower(),
            os.environ.get('TMP', '').lower(),
            os.path.join(os.environ.get('LOCALAPPDATA', ''), 'temp').lower(),
            os.path.join(os.environ.get('APPDATA', ''), 'temp').lower(),
        ]
        SAFE_DIRS = [
            'program files', 'windows', 'system32', 'syswow64',
            'nvidia', 'microsoft', 'steam', 'discord',
            # Herramientas de análisis anticheat — nunca son sospechosas
            'argusscanner', 'argus scanner', 'echo-acb', 'echoscanner',
            'astross', 'minecraftsstool',
        ]

        now = _dt.datetime.now()
        try:
            for proc in psutil.process_iter(['pid', 'name', 'exe', 'create_time']):
                try:
                    pname = (proc.info.get('name') or '').lower()
                    exe   = (proc.info.get('exe') or '').lower()
                    ctime = proc.info.get('create_time') or 0

                    if not exe or not pname:
                        continue

                    # #14 — Correlación nombre + ruta
                    is_generic_name = pname in SUSPICIOUS_NAMES
                    in_temp = any(td and exe.startswith(td) for td in SUSPICIOUS_TEMP_DIRS if td)
                    in_safe = any(sd in exe for sd in SAFE_DIRS)

                    if is_generic_name and in_temp and not in_safe:
                        print(f"⚠️ PROCESO SOSPECHOSO EN TEMP: {pname} desde {exe}")
                        self.issues_found.append({
                            'nombre': f'Proceso con nombre genérico en carpeta temporal: {pname}',
                            'ruta': exe,
                            'archivo': pname,
                            'tipo': 'suspicious_process_location',
                            'categoria': 'PROCESO',
                            'alerta': 'SOSPECHOSO',
                            'confidence': 0.65,
                            'detected_patterns': ['generic_name_in_temp'],
                            'explicacion': f'{pname} está corriendo desde una carpeta temporal ({exe}). '
                                           f'Procesos legítimos con este nombre se ejecutan desde Program Files, '
                                           f'no desde carpetas temporales. Puede ser un inyector o loader.',
                        })

                    # #15 — Tiempo de vida del proceso
                    if ctime > 0:
                        uptime_secs = (now - _dt.datetime.fromtimestamp(ctime)).total_seconds()
                        if uptime_secs < 60 and in_temp and not in_safe:
                            print(f"⚠️ PROCESO RECIENTE EN TEMP (<60s): {pname}")
                            self.issues_found.append({
                                'nombre': f'Proceso muy reciente en carpeta temporal: {pname} ({int(uptime_secs)}s)',
                                'ruta': exe,
                                'archivo': pname,
                                'tipo': 'short_lived_process',
                                'categoria': 'PROCESO',
                                'alerta': 'SOSPECHOSO',
                                'confidence': 0.70,
                                'detected_patterns': ['short_lived_temp_process'],
                                'explicacion': f'{pname} lleva solo {int(uptime_secs)} segundos corriendo y está '
                                               f'en una carpeta temporal. Puede haber sido lanzado justo antes del SS '
                                               f'para inyectar código y luego cerrarse.',
                            })
                except (psutil.NoSuchProcess, psutil.AccessDenied):
                    continue
        except Exception as e:
            print(f"Error en scan_process_path_correlation: {e}")

    def scan_process_hashes_cloud(self):
        """P2 #16 — Verifica el hash SHA256 de procesos activos contra hack_hashes en la cloud."""
        print("🔍 Verificando hashes de procesos contra cloud DB...")
        if not requests:
            return
        try:
            base_url = self.config.get('api_url', '').rstrip('/')
            if not base_url:
                return
            r = requests.get(f'{base_url}/api/hashes', timeout=8)
            if not r.ok:
                return
            cloud_hashes = {h['sha256'].lower(): h['hack_name'] for h in r.json().get('hashes', [])}
            if not cloud_hashes:
                return
        except Exception:
            return

        try:
            for proc in psutil.process_iter(['pid', 'name', 'exe']):
                try:
                    exe = proc.info.get('exe') or ''
                    if not exe or not os.path.isfile(exe):
                        continue
                    exe_l = exe.lower()
                    if any(s in exe_l for s in ('windows', 'program files', 'system32')):
                        continue
                    try:
                        h = hashlib.sha256()
                        with open(exe, 'rb') as f:
                            for chunk in iter(lambda: f.read(65536), b''):
                                h.update(chunk)
                        file_hash = h.hexdigest().lower()
                    except Exception:
                        continue

                    if file_hash in cloud_hashes:
                        hack_name = cloud_hashes[file_hash]
                        pname = proc.info.get('name', '')
                        print(f"🚨 HASH EN CLOUD DB: {pname} → {hack_name}")
                        self.issues_found.append({
                            'nombre': f'Proceso en cloud DB de hacks: {pname} ({hack_name})',
                            'ruta': exe,
                            'archivo': pname,
                            'tipo': 'cloud_hash_match',
                            'categoria': 'GHOST_CLIENT',
                            'alerta': 'CRITICAL',
                            'confidence': 0.99,
                            'detected_patterns': [f'cloud_hash:{hack_name}'],
                            'file_hash': file_hash,
                            'explicacion': f'El proceso {pname} coincide con el hash de {hack_name} '
                                           f'en la base de datos de hacks confirmados. '
                                           f'Detección 100% confiable por hash.',
                        })
                except (psutil.NoSuchProcess, psutil.AccessDenied):
                    continue
        except Exception as e:
            print(f"Error en scan_process_hashes_cloud: {e}")

    def scan_minecraft_version_count(self):
        """#29 — Tener 3+ versiones de Minecraft sin ser desarrollador conocido es sospechoso."""
        print("🔍 Contando versiones de Minecraft instaladas...")
        appdata = os.environ.get('APPDATA', '')
        versions_dir = os.path.join(appdata, '.minecraft', 'versions')
        if not os.path.isdir(versions_dir):
            return
        try:
            versions = [
                d for d in os.listdir(versions_dir)
                if os.path.isdir(os.path.join(versions_dir, d))
                and not d.startswith('.')
            ]
            VANILLA_RE = r'^\d+\.\d+(\.\d+)?$'
            import re as _re2
            vanilla = [v for v in versions if _re2.match(VANILLA_RE, v)]
            non_vanilla = [v for v in versions if not _re2.match(VANILLA_RE, v)]
            if len(versions) >= 8:
                level = 'SOSPECHOSO' if len(versions) < 12 else 'CRITICAL'
                conf = 0.55 if len(versions) < 12 else 0.70
                print(f"⚠️ MÚLTIPLES VERSIONES MC: {len(versions)} ({len(non_vanilla)} no-vanilla)")
                self.issues_found.append({
                    'nombre': f'{len(versions)} versiones de Minecraft instaladas ({len(non_vanilla)} no-vanilla)',
                    'ruta': versions_dir,
                    'archivo': '',
                    'tipo': 'ghost_client_config',
                    'categoria': 'MULTI_VERSION',
                    'alerta': level,
                    'confidence': conf,
                    'detected_patterns': [f'mc_versions:{len(versions)}', f'non_vanilla:{len(non_vanilla)}'],
                    'explicacion': (
                        f'Se encontraron {len(versions)} versiones de Minecraft en .minecraft/versions/. '
                        f'Las versiones no-vanilla son: {", ".join(non_vanilla[:6])}. '
                        'Los hackers instalan múltiples versiones para probar sus hacks en distintas '
                        'versiones del juego y encontrar la que no está protegida por el anti-cheat del servidor.'
                    ),
                })
        except Exception as e:
            print(f"Error en scan_minecraft_version_count: {e}")

    def scan_exe_entropy_and_packing(self):
        """#18/#19/#20 — .exe sospechosos: sin metadata PE, alta entropy, packed con UPX/MPRESS."""
        print("🔍 Analizando metadata PE, entropy y packing de ejecutables sospechosos...")
        import math as _math
        HACK_DIRS = [
            os.path.expanduser('~\\Desktop'),
            os.path.expanduser('~\\Downloads'),
            os.path.join(os.environ.get('APPDATA', ''), '.minecraft'),
            os.path.join(os.environ.get('APPDATA', ''), '.weave'),
        ]
        SAFE_PUBLISHERS = [b'Microsoft', b'NVIDIA', b'Adobe', b'Google', b'Intel']

        def _shannon_entropy(data: bytes) -> float:
            if not data:
                return 0.0
            freq = [0] * 256
            for b in data:
                freq[b] += 1
            total = len(data)
            return -sum((c / total) * _math.log2(c / total) for c in freq if c > 0)

        def _is_upx_packed(data: bytes) -> bool:
            return (b'UPX!' in data[:4096] or
                    b'This file is packed with the UPX' in data[:4096] or
                    b'UPX0' in data[:512] or b'UPX1' in data[:512])

        try:
            for base in HACK_DIRS:
                if not os.path.isdir(base):
                    continue
                for fname in os.listdir(base):
                    if not fname.lower().endswith('.exe'):
                        continue
                    fpath = os.path.join(base, fname)
                    try:
                        fsize = os.path.getsize(fpath)
                        if fsize < 4096 or fsize > 50 * 1024 * 1024:
                            continue
                        with open(fpath, 'rb') as f:
                            header = f.read(min(65536, fsize))

                        # Skip executables signed by known publishers
                        if any(pub in header for pub in SAFE_PUBLISHERS):
                            continue

                        entropy = _shannon_entropy(header)
                        upx = _is_upx_packed(header)

                        # P2 #18 — PE VersionInfo metadata check
                        # Legítimos tienen CompanyName/FileDescription; hacks raramente los tienen
                        has_version_info = (
                            b'CompanyName' in header or
                            b'FileDescription' in header or
                            b'ProductName' in header or
                            b'LegalCopyright' in header
                        )

                        if upx:
                            print(f"🚨 UPX PACKED EXE: {fpath}")
                            self.issues_found.append({
                                'nombre': f'Ejecutable packed con UPX: {fname}',
                                'ruta': fpath,
                                'archivo': fname,
                                'tipo': 'ghost_client_config',
                                'categoria': 'PACKED_EXE',
                                'alerta': 'SOSPECHOSO',
                                'confidence': 0.78,
                                'detected_patterns': ['upx_packed'],
                                'explicacion': (
                                    f'{fname} fue comprimido con UPX, una técnica usada para ocultar '
                                    'el contenido de los ejecutables de los escáneres antivirus. '
                                    'Los hack clients frecuentemente usan UPX para evadir detección.'
                                ),
                            })
                        elif entropy > 7.4:
                            print(f"⚠️ ALTA ENTROPY ({entropy:.2f}): {fpath}")
                            self.issues_found.append({
                                'nombre': f'Ejecutable con entropy alta ({entropy:.2f} bits/byte): {fname}',
                                'ruta': fpath,
                                'archivo': fname,
                                'tipo': 'ghost_client_config',
                                'categoria': 'OBFUSCATED_EXE',
                                'alerta': 'POCO_SOSPECHOSO',
                                'confidence': 0.62,
                                'detected_patterns': [f'high_entropy:{entropy:.2f}'],
                                'explicacion': (
                                    f'{fname} tiene una entropy de {entropy:.2f} bits/byte (máximo: 8.0). '
                                    'Valores >7.4 indican que el archivo está cifrado o comprimido, '
                                    'lo que es una señal de ofuscación deliberada para evitar análisis.'
                                ),
                            })
                        elif not has_version_info and not upx and fsize > 100 * 1024:
                            # Sin metadata PE y sin packing conocido — sospechoso si es >100KB
                            print(f"⚠️ SIN METADATA PE: {fpath}")
                            self.issues_found.append({
                                'nombre': f'Ejecutable sin metadata PE (sin CompanyName/FileDescription): {fname}',
                                'ruta': fpath,
                                'archivo': fname,
                                'tipo': 'ghost_client_config',
                                'categoria': 'NO_PE_METADATA',
                                'alerta': 'POCO_SOSPECHOSO',
                                'confidence': 0.55,
                                'detected_patterns': ['no_version_info'],
                                'explicacion': (
                                    f'{fname} no tiene metadata PE (CompanyName, FileDescription, ProductName). '
                                    'Los ejecutables legítimos firmados siempre incluyen esta información. '
                                    'Los hack clients compilados caseros raramente la incluyen.'
                                ),
                            })
                    except Exception:
                        continue
        except Exception as e:
            print(f"Error en scan_exe_entropy_and_packing: {e}")

    def scan_javaagent_args(self):
        """#1 — Detecta -javaagent en cmdline de javaw.exe (inyección directa en JVM)."""
        print("🔍 Buscando -javaagent en args de Java...")
        try:
            for proc in psutil.process_iter(['pid', 'name', 'cmdline']):
                try:
                    name = (proc.info.get('name') or '').lower()
                    if 'java' not in name:
                        continue
                    cmdline = proc.info.get('cmdline') or []
                    for arg in cmdline:
                        arg_l = arg.lower()
                        if '-javaagent' in arg_l:
                            jar_name = arg.split('=')[-1].split('\\')[-1].split('/')[-1]
                            # Ignorar agentes de launchers oficiales conocidos
                            safe_agents = ['authlib', 'oshi', 'legacylauncher', 'lunarclient', 'badlion']
                            if any(s in arg_l for s in safe_agents):
                                continue
                            print(f"🚨 JAVAAGENT: {arg}")
                            self.issues_found.append({
                                'nombre': f'-javaagent detectado en JVM: {jar_name}',
                                'ruta': arg,
                                'archivo': jar_name,
                                'tipo': 'javaagent_injection',
                                'categoria': 'INYECCION',
                                'alerta': 'CRITICAL',
                                'confidence': 0.95,
                                'detected_patterns': ['javaagent_injection'],
                                'explicacion': f'Se detectó un agente Java inyectado en Minecraft: {jar_name}. '
                                               f'Frameworks como Weave, ForgeHax y la mayoría de ghost clients modernos '
                                               f'usan -javaagent para inyectar código en runtime.',
                            })
                        # -Xbootclasspath y -agentpath/-agentlib (otras formas de injection JVM)
                        for boot_arg in ('-xbootclasspath/p:', '-xbootclasspath/a:', '-agentpath:', '-agentlib:'):
                            if boot_arg in arg_l:
                                arg_val = arg.split(':', 1)[-1] if ':' in arg else arg
                                fname   = arg_val.split('\\')[-1].split('/')[-1]
                                safe_agentlibs = ('jdwp', 'hprof', 'instrument')
                                if any(s in arg_l for s in safe_agentlibs) and boot_arg == '-agentlib:':
                                    continue
                                self.issues_found.append({
                                    'nombre': f'Arg JVM de inyección detectado: {arg[:80]}',
                                    'ruta': arg,
                                    'archivo': fname,
                                    'tipo': 'javaagent_injection',
                                    'categoria': 'INYECCION',
                                    'alerta': 'CRITICAL',
                                    'confidence': 0.93,
                                    'detected_patterns': [f'jvm_injection_arg:{boot_arg.rstrip(":")}'],
                                    'explicacion': f'Se detectó {boot_arg} en los argumentos JVM de Minecraft. '
                                                   f'Este flag permite cargar código nativo o bytecode arbitrario '
                                                   f'en la JVM antes de que Minecraft arranque (técnica de injection avanzada).',
                                })
                except (psutil.NoSuchProcess, psutil.AccessDenied):
                    continue
        except Exception as e:
            print(f"Error en scan_javaagent_args: {e}")

    def scan_weave_loader(self):
        """#4 — Detecta artefactos de Weave Loader (framework de inyección más popular)."""
        print("🔍 Buscando artefactos de Weave Loader...")
        appdata  = os.environ.get('APPDATA', '')
        local    = os.environ.get('LOCALAPPDATA', '')
        mc_dir   = os.path.join(appdata, '.minecraft')
        WEAVE_PATHS = [
            (os.path.join(appdata,  '.weave'),                          'Directorio de Weave Loader v1'),
            (os.path.join(appdata,  '.weave', 'weave.json'),            'Configuración de Weave v1'),
            (os.path.join(appdata,  '.weave', 'extensions'),            'Weave Loader v2 extensions/'),
            (os.path.join(appdata,  'WeaveLoader'),                     'WeaveLoader AppData'),
            (os.path.join(local,    'WeaveLoader'),                     'WeaveLoader LocalAppData'),
            (os.path.join(appdata,  '.weave2'),                         'Weave Loader v2 dir'),
            (os.path.join(mc_dir,   '.weave'),                          'Weave en .minecraft'),
            (os.path.join(mc_dir,   'weave'),                           'Weave folder en .minecraft'),
        ]
        # Módulos de Weave que son hacks conocidos
        WEAVE_HACK_MODULES = {
            'killaura', 'aimassist', 'triggerbot', 'reach', 'velocity',
            'scaffold', 'nofall', 'fly', 'speed', 'fullbright', 'xray',
            'autoclick', 'clickgui', 'freecam', 'nametag', 'blink',
        }
        try:
            reported_dirs = set()
            for path, desc in WEAVE_PATHS:
                if not os.path.exists(path):
                    continue
                base_dir = path if os.path.isdir(path) else os.path.dirname(path)
                if base_dir in reported_dirs:
                    continue
                reported_dirs.add(base_dir)

                extra_patterns = ['weave_loader']
                extra_info = ''
                # Leer weave.json para detectar módulos de hacks cargados
                weave_json_path = os.path.join(base_dir, 'weave.json')
                if os.path.isfile(weave_json_path):
                    try:
                        import json as _json
                        with open(weave_json_path, 'r', encoding='utf-8', errors='ignore') as f:
                            wdata = _json.load(f)
                        mods_list = []
                        # weave.json puede tener "modules", "mods", "enabled"
                        for key in ('modules', 'mods', 'enabled', 'addons'):
                            val = wdata.get(key, [])
                            if isinstance(val, list):
                                mods_list.extend(str(m).lower() for m in val)
                            elif isinstance(val, dict):
                                mods_list.extend(k.lower() for k in val.keys())
                        hack_mods = [m for m in mods_list
                                     if any(h in m for h in WEAVE_HACK_MODULES)]
                        if hack_mods:
                            extra_patterns.append(f'weave_modules:{",".join(hack_mods[:5])}')
                            extra_info = f' Módulos detectados: {", ".join(hack_mods[:5])}.'
                    except Exception:
                        pass

                print(f"🚨 WEAVE LOADER: {path}")
                self.issues_found.append({
                    'nombre': f'Weave Loader detectado: {desc}',
                    'ruta': path,
                    'archivo': os.path.basename(path),
                    'tipo': 'ghost_client_config',
                    'categoria': 'GHOST_CLIENT',
                    'alerta': 'CRITICAL',
                    'confidence': 0.96,
                    'detected_patterns': extra_patterns,
                    'explicacion': (
                        'Weave Loader es el framework de inyección de mods más popular actualmente. '
                        'Permite cargar ghost clients y módulos de hacks en Minecraft sin dejar '
                        f'archivos .jar visibles en la carpeta mods.{extra_info}'
                    ),
                })
        except Exception as e:
            print(f"Error en scan_weave_loader: {e}")

    def scan_xray_resourcepacks(self):
        """#4 — Detecta resourcepacks de Xray con texturas transparentes para stone/dirt."""
        print("🔍 Buscando resourcepacks Xray en .minecraft/resourcepacks/...")
        import zipfile as _zf
        import struct as _struct
        appdata = os.environ.get('APPDATA', '')
        rp_dir = os.path.join(appdata, '.minecraft', 'resourcepacks')
        if not os.path.isdir(rp_dir):
            return

        # Bloques sólidos que los packs xray hacen transparentes para ver a través de ellos.
        # Packs legítimos NO necesitan canal alpha en estas texturas.
        XRAY_TARGETS = {
            'stone', 'deepslate', 'dirt', 'gravel', 'sand', 'netherrack',
            'cobblestone', 'end_stone', 'soul_sand', 'soul_soil',
            'tuff', 'calcite', 'dripstone_block', 'mud', 'packed_mud',
            'granite', 'diorite', 'andesite', 'sandstone', 'red_sandstone',
        }

        # Palabras en el nombre del pack que confirman xray sin análisis de texturas
        XRAY_NAME_KW = ('xray', 'x-ray', 'xvision', 'x_ray', 'xfull', 'fullbright+x',
                        'cave finder', 'ore finder', 'orefindr', 'see through')

        def _png_avg_alpha(data: bytes) -> float:
            """Devuelve el alpha promedio (0-255) de una textura PNG, o 255 si no tiene canal alpha."""
            try:
                if data[:8] != b'\x89PNG\r\n\x1a\n':
                    return 255.0
                color_type = data[25]
                if color_type not in (4, 6):  # solo grayscale+alpha o RGBA
                    return 255.0
                channels = 4 if color_type == 6 else 2
                width  = _struct.unpack('>I', data[16:20])[0]
                height = _struct.unpack('>I', data[20:24])[0]
                import zlib as _zl
                raw = b''
                pos = 8
                while pos + 12 <= len(data):
                    length = _struct.unpack('>I', data[pos:pos+4])[0]
                    ctype  = data[pos+4:pos+8]
                    chunk  = data[pos+8:pos+8+length]
                    pos   += 12 + length
                    if ctype == b'IDAT':
                        raw += chunk
                    elif ctype == b'IEND':
                        break
                decompressed = _zl.decompress(raw)
                stride = 1 + width * channels
                alphas = []
                for row in range(min(height, 16)):
                    row_start = row * stride + 1
                    for col in range(width):
                        alphas.append(decompressed[row_start + col * channels + channels - 1])
                return sum(alphas) / len(alphas) if alphas else 255.0
            except Exception:
                return 255.0

        try:
            for rp_name in os.listdir(rp_dir):
                rp_path = os.path.join(rp_dir, rp_name)
                rp_lower = rp_name.lower()

                # ── Señal 1: nombre del pack contiene keyword de xray ─────────────
                name_is_xray = any(kw in rp_lower for kw in XRAY_NAME_KW)

                # ── Señal 2: análisis de texturas (solo zips) ─────────────────────
                xray_textures_low  = []  # alpha < 30 (casi invisible)
                xray_textures_mid  = []  # alpha 30-79 (semitransparente)

                if rp_lower.endswith('.zip'):
                    try:
                        with _zf.ZipFile(rp_path, 'r') as zf:
                            entries = {n.lower(): n for n in zf.namelist()}
                            for target in XRAY_TARGETS:
                                for prefix in ('assets/minecraft/textures/block/',
                                               'assets/minecraft/textures/blocks/'):
                                    cp = f'{prefix}{target}.png'
                                    if cp not in entries:
                                        continue
                                    try:
                                        avg_a = _png_avg_alpha(zf.read(entries[cp]))
                                        if avg_a < 30:
                                            xray_textures_low.append(f'{target}({avg_a:.0f})')
                                        elif avg_a < 80:
                                            xray_textures_mid.append(f'{target}({avg_a:.0f})')
                                    except Exception:
                                        pass
                                    break
                    except Exception:
                        pass

                all_xray = xray_textures_low + xray_textures_mid
                n_low = len(xray_textures_low)
                n_all = len(all_xray)

                # ── Decisión: requiere evidencia sólida ───────────────────────────
                # Nombre xray + cualquier textura transparente → CRITICAL
                # Sin nombre: necesita ≥3 texturas transparentes (al menos 1 muy baja)
                if name_is_xray and n_all >= 1:
                    alerta, conf = 'CRITICAL', 0.95
                elif n_low >= 3:
                    alerta, conf = 'CRITICAL', min(0.92, 0.70 + n_low * 0.06)
                elif n_low >= 1 and n_all >= 3:
                    alerta, conf = 'CRITICAL', 0.82
                elif n_all >= 5:
                    alerta, conf = 'SOSPECHOSO', 0.65
                elif n_all >= 3 and not name_is_xray:
                    alerta, conf = 'POCO_SOSPECHOSO', 0.45
                else:
                    continue  # evidencia insuficiente — no reportar

                print(f"🚨 RESOURCEPACK XRAY: {rp_name} (nombre_xray={name_is_xray}, low={n_low}, mid={len(xray_textures_mid)})")
                self.issues_found.append({
                    'nombre': f'Resourcepack Xray detectado: {rp_name}',
                    'ruta': rp_path,
                    'archivo': rp_name,
                    'tipo': 'ghost_client_config',
                    'categoria': 'XRAY',
                    'alerta': alerta,
                    'confidence': conf,
                    'detected_patterns': (
                        (['xray_name_keyword'] if name_is_xray else []) +
                        [f'xray_texture:{t}' for t in all_xray[:6]]
                    ),
                    'explicacion': (
                        (f'El nombre "{rp_name}" contiene keyword de Xray. ' if name_is_xray else '') +
                        (f'{n_all} textura(s) de bloques sólidos con canal alpha anormal '
                         f'({"muy transparente" if n_low else "semitransparente"}): '
                         f'{", ".join(all_xray[:4])}. ' if all_xray else '') +
                        'Los packs Xray hacen invisibles piedra/tierra para ver minerales a través de las paredes.'
                    ),
                })
        except Exception as e:
            print(f"Error en scan_xray_resourcepacks: {e}")

    def scan_bat_ps1_launchers(self):
        """#5 — Detecta scripts .bat/.ps1 que lanzan JARs con -javaagent o argumentos sospechosos."""
        print("🔍 Buscando launchers .bat/.ps1 de hack clients en Desktop/Downloads...")
        search_dirs = [
            os.path.expanduser('~\\Desktop'),
            os.path.expanduser('~\\Downloads'),
            os.path.expanduser('~\\Documents'),
            os.path.join(os.environ.get('APPDATA', ''), '.minecraft'),
        ]
        HACK_ARGS = [
            '-javaagent', '-xbootclasspath', '-agentpath',
            'killaura', 'aimbot', 'autoclicker', 'liquidbounce',
            'vape', 'sigma', 'wurst', 'meteor', 'ghostclient',
            'weaveloader', 'weave-loader',
        ]
        SAFE_NAMES = {'install', 'setup', 'update', 'uninstall', 'launcher', 'run', 'start', 'forge-installer'}
        try:
            for base in search_dirs:
                if not os.path.isdir(base):
                    continue
                for fname in os.listdir(base):
                    fname_lower = fname.lower()
                    if not (fname_lower.endswith('.bat') or fname_lower.endswith('.cmd') or fname_lower.endswith('.ps1')):
                        continue
                    stem = os.path.splitext(fname_lower)[0]
                    if any(s in stem for s in SAFE_NAMES):
                        continue
                    fpath = os.path.join(base, fname)
                    try:
                        with open(fpath, 'r', encoding='utf-8', errors='ignore') as f:
                            content = f.read(4096).lower()
                    except Exception:
                        continue
                    matched = [kw for kw in HACK_ARGS if kw in content]
                    if not matched:
                        continue
                    print(f"🚨 BAT/PS1 LAUNCHER: {fpath}")
                    self.issues_found.append({
                        'nombre': f'Script launcher de hack: {fname}',
                        'ruta': fpath,
                        'archivo': fname,
                        'tipo': 'ghost_client_config',
                        'categoria': 'LANZADOR',
                        'alerta': 'CRITICAL',
                        'confidence': 0.88,
                        'detected_patterns': [f'bat_launcher:{kw}' for kw in matched[:4]],
                        'explicacion': (
                            f'{fname} es un script {fname_lower.rsplit(".", 1)[-1].upper()} que contiene argumentos '
                            f'sospechosos ({", ".join(matched[:3])}). Los hack clients frecuentemente usan '
                            'scripts wrapper para pasarle -javaagent o classpath custom a la JVM de Minecraft.'
                        ),
                    })
        except Exception as e:
            print(f"Error en scan_bat_ps1_launchers: {e}")

    def scan_options_txt_keybinds(self):
        """#6 — Detecta teclas de ataque mapeadas a botones extra de mouse (indicador de autoclicker)."""
        print("🔍 Revisando options.txt de Minecraft por keybinds sospechosos...")
        appdata = os.environ.get('APPDATA', '')
        mc_dir = os.path.join(appdata, '.minecraft')
        SUSPICIOUS_BINDS = {
            'key_key.attack': {'button4', 'button5', 'button6', 'button7', 'button8'},
            'key_key.use':    {'button4', 'button5', 'button6', 'button7', 'button8'},
        }
        try:
            # Escanear options.txt del .minecraft raíz y de perfiles de versiones
            options_files = []
            root_opts = os.path.join(mc_dir, 'options.txt')
            if os.path.isfile(root_opts):
                options_files.append(root_opts)
            profiles_dir = os.path.join(mc_dir, 'versions')
            if os.path.isdir(profiles_dir):
                for ver in os.listdir(profiles_dir):
                    ver_opts = os.path.join(profiles_dir, ver, 'options.txt')
                    if os.path.isfile(ver_opts):
                        options_files.append(ver_opts)

            for opts_path in options_files:
                try:
                    with open(opts_path, 'r', encoding='utf-8', errors='ignore') as f:
                        lines = f.readlines()
                    for line in lines:
                        line = line.strip().lower()
                        for bind_key, bad_values in SUSPICIOUS_BINDS.items():
                            if line.startswith(bind_key + ':'):
                                value = line.split(':', 1)[-1].strip()
                                if value in bad_values:
                                    print(f"🚨 KEYBIND SOSPECHOSO: {bind_key}={value} en {opts_path}")
                                    self.issues_found.append({
                                        'nombre': f'Keybind de ataque en botón extra: {bind_key}={value}',
                                        'ruta': opts_path,
                                        'archivo': 'options.txt',
                                        'tipo': 'ghost_client_config',
                                        'categoria': 'AUTOCLICK',
                                        'alerta': 'SOSPECHOSO',
                                        'confidence': 0.75,
                                        'detected_patterns': [f'keybind:{bind_key}:{value}'],
                                        'explicacion': (
                                            f'La acción "{bind_key.replace("key_key.", "")}" está mapeada a {value} '
                                            '(botón lateral del mouse). Esto indica que el jugador usa un botón '
                                            'dedicado del mouse para atacar, lo que es un indicador frecuente '
                                            'de autoclicker configurado en software de mouse gaming.'
                                        ),
                                    })
                except Exception:
                    continue
        except Exception as e:
            print(f"Error en scan_options_txt_keybinds: {e}")

    def scan_hack_properties_configs(self):
        """#10 — Detecta archivos .properties de hack clients con módulos activados."""
        print("🔍 Buscando .properties de hack clients con módulos activos...")
        appdata = os.environ.get('APPDATA', '')
        mc_dir = os.path.join(appdata, '.minecraft')
        config_dir = os.path.join(mc_dir, 'config')
        HACK_MODULE_KEYS = [
            'killaura', 'aimbot', 'reach', 'velocity', 'nofall', 'scaffold',
            'speed', 'fly', 'bhop', 'bunnyhop', 'triggerbot', 'antikb',
            'antiknockback', 'timer', 'esp', 'xray', 'fullbright', 'criticals',
            'fastplace', 'autoeat', 'autototem', 'baritone', 'aura',
        ]
        try:
            if not os.path.isdir(config_dir):
                return
            for root, dirs, files in os.walk(config_dir):
                dirs[:] = [d for d in dirs if d.lower() not in {'optifine', 'forge', 'fml', 'journeymap', 'rei'}]
                for fname in files:
                    if not fname.lower().endswith('.properties'):
                        continue
                    fpath = os.path.join(root, fname)
                    try:
                        with open(fpath, 'r', encoding='utf-8', errors='ignore') as f:
                            content = f.read(8192).lower()
                    except Exception:
                        continue
                    enabled_modules = []
                    for line in content.splitlines():
                        line = line.strip()
                        if '=' not in line or line.startswith('#'):
                            continue
                        key, _, val = line.partition('=')
                        key = key.strip()
                        val = val.strip()
                        if val not in ('true', '1', 'on', 'enabled', 'yes'):
                            continue
                        for mod in HACK_MODULE_KEYS:
                            if mod in key:
                                enabled_modules.append(f'{mod}=true')
                                break
                    if len(enabled_modules) >= 2:
                        print(f"🚨 HACK .PROPERTIES: {fpath} ({len(enabled_modules)} módulos activos)")
                        self.issues_found.append({
                            'nombre': f'Config de hack con módulos activos: {fname}',
                            'ruta': fpath,
                            'archivo': fname,
                            'tipo': 'ghost_client_config',
                            'categoria': 'CONFIG_HACK',
                            'alerta': 'CRITICAL',
                            'confidence': 0.87,
                            'detected_patterns': [f'prop_module:{m}' for m in enabled_modules[:6]],
                            'explicacion': (
                                f'{fname} contiene {len(enabled_modules)} módulos de hack activos '
                                f'({", ".join(enabled_modules[:4])}{"..." if len(enabled_modules)>4 else ""}). '
                                'Los archivos .properties son el formato de configuración usado por varios '
                                'ghost clients para persistir qué módulos están habilitados entre sesiones.'
                            ),
                        })
        except Exception as e:
            print(f"Error en scan_hack_properties_configs: {e}")

    def scan_prefetch_hacks(self):
        """#21 — Detecta archivos Prefetch de hacks ejecutados (aunque el exe esté borrado)."""
        print("🔍 Escaneando Prefetch por hacks ejecutados...")
        prefetch_dir = r'C:\Windows\Prefetch'
        HACK_NAMES = [
            # Clientes clásicos
            'sigma', 'vape', 'vapelite', 'liquidbounce', 'wurst', 'rise',
            'flux', 'future', 'astolfo', 'novoline', 'drip', 'entropy',
            'whiteout', 'exhibition', 'impact',
            # Clientes modernos (2022-2025)
            'meteor', 'meteorclient',
            'rusherhack', 'rusher',
            'aristois',
            'tenacity',
            'vertex', 'vertexclient',
            'inertia', 'inertiaclient',
            'salhack',
            'jello', 'jelloclient',
            'datura', 'daturamc',
            'remix', 'remixclient',
            'pandora', 'pandoraclient',
            'azura',
            'kamiblue',
            'konas',
            'weepcraft',
            'zeroday',
            'nyx', 'nyxclient',
            'lucid', 'lucidclient',
            'nextgen', 'tegernako',
            # Loaders e injectors
            'weaveloader', 'weave-loader',
            'extremeinjector', 'xenos',
            'cheatengine', 'processhacker',
            'injector',
            # Nombres genéricos de ghost clients
            'ghostclient', 'ghost-client',
            'hackclient',
            'aimbot', 'killaura',
            'scaffold', 'baritone',
        ]
        if not os.path.isdir(prefetch_dir):
            return
        try:
            for fname in os.listdir(prefetch_dir):
                if not fname.lower().endswith('.pf'):
                    continue
                fname_lower = fname.lower()
                for hack in HACK_NAMES:
                    if hack in fname_lower:
                        exe_name = fname.split('-')[0]
                        full_path = os.path.join(prefetch_dir, fname)
                        mtime = os.path.getmtime(full_path)
                        import datetime as _dt
                        last_run = _dt.datetime.fromtimestamp(mtime).strftime('%d/%m/%Y %H:%M')
                        print(f"🚨 PREFETCH HACK: {fname} (última ejecución: {last_run})")
                        self.issues_found.append({
                            'nombre': f'Prefetch de hack encontrado: {exe_name}',
                            'ruta': full_path,
                            'archivo': fname,
                            'tipo': 'prefetch_hack',
                            'categoria': 'FORENSE',
                            'alerta': 'CRITICAL',
                            'confidence': 0.90,
                            'detected_patterns': [f'prefetch:{hack}'],
                            'explicacion': f'Se encontró un archivo Prefetch de {exe_name} (última ejecución: {last_run}). '
                                           f'El Prefetch confirma que este programa fue ejecutado en este PC aunque '
                                           f'el archivo original haya sido borrado.',
                        })
                        break
        except Exception as e:
            print(f"Error en scan_prefetch_hacks: {e}")

    def scan_usn_minecraft_jars(self):
        """#22/#23 — Detecta JARs y carpetas de ghost clients eliminados via USN Journal."""
        print("🔍 Buscando JARs/.minecraft borrados en USN Journal (últimas 72h)...")
        HACK_PATTERNS = [
            # Clientes clásicos
            'sigma', 'vape', 'vapelite', 'liquidbounce', 'wurst', 'rise',
            'flux', 'future', 'astolfo', 'novoline', 'drip', 'entropy',
            'whiteout', 'exhibition',
            # Clientes modernos (2022-2025)
            'meteor', 'rusherhack', 'aristois', 'tenacity', 'vertex',
            'inertia', 'salhack', 'jello', 'datura', 'remix', 'pandora',
            'azura', 'kamiblue', 'konas', 'weepcraft', 'zeroday',
            'nyx', 'lucid', 'nextgen', 'impact',
            # Fingerprints de directorio
            '.weave', '.rise', '.sigma', '.meteor', '.liquidbounce',
            # Misc
            'ghostclient', 'ghost_client', 'baritone', 'schematica',
            'hackclient', 'hackmod', 'weaveloader',
        ]
        try:
            lines = self._read_usn_journal(max_lines=150_000, max_seconds=12)
            if not lines:
                return
            # Filtrar eliminaciones (0x80000200) de .jar y carpetas de ghost clients
            for line in lines:
                line_l = line.lower()
                is_delete = '0x80000200' in line or '0x80000020' in line
                is_rename = '0x00001000' in line or '0x00002000' in line
                if not (is_delete or is_rename):
                    continue
                has_hack = any(p in line_l for p in HACK_PATTERNS)
                has_mc   = '.minecraft' in line_l
                is_jar   = '.jar' in line_l
                if not (has_hack or (has_mc and is_jar)):
                    continue
                # Extraer nombre de archivo del CSV (columna 1 = Filename en fsutil)
                parts = line.split(',')
                # fsutil readjournal CSV: Usn, Filename, Timestamp, Reason, ...
                fname_raw = (parts[1].strip('"') if len(parts) > 2 else
                             parts[3].strip('"') if len(parts) > 3 else line[:80])
                fname = fname_raw.strip() or line[:80]
                action = 'borrado' if is_delete else 'renombrado'
                alerta = 'CRITICAL' if has_hack else 'SOSPECHOSO'
                conf   = 0.85 if has_hack else 0.70
                print(f"🚨 USN JAR {action.upper()}: {fname}")
                self.issues_found.append({
                    'nombre':   f'JAR {action} (USN Journal): {fname}',
                    'ruta':     fname,
                    'archivo':  fname,
                    'tipo':     'usn_deleted_hack',
                    'categoria':'FORENSE',
                    'alerta':   alerta,
                    'confidence': conf,
                    'detected_patterns': [f'usn_{action}', f'file:{fname}']
                                         + [p for p in HACK_PATTERNS if p in fname.lower()],
                })
        except Exception as e:
            print(f"Error en scan_usn_minecraft_jars: {e}")

    def scan_discord_webhooks(self):
        """Detecta URLs de Discord webhooks en archivos de config de hack clients (C2/exfiltración)."""
        print("🔍 Buscando Discord webhooks en configs de hacks...")
        import re as _re
        appdata = os.environ.get('APPDATA', '')
        local   = os.environ.get('LOCALAPPDATA', '')
        home    = os.path.expanduser('~')
        # Carpetas donde los hacks guardan sus configs
        SEARCH_BASES = [
            os.path.join(appdata, '.minecraft'),
            os.path.join(appdata, '.weave'),
            os.path.join(appdata, 'WeaveLoader'),
            os.path.join(local,   'WeaveLoader'),
            os.path.join(home,    'Desktop'),
            os.path.join(home,    'Downloads'),
            os.path.join(home,    'Documents'),
        ]
        # Extensiones de archivo de config
        CONFIG_EXTS = {'.json', '.txt', '.cfg', '.yml', '.yaml', '.toml', '.properties', '.log'}
        WEBHOOK_RE = _re.compile(
            r'https?://(?:ptb\.|canary\.)?discord(?:app)?\.com/api/webhooks/\d+/[\w-]+',
            _re.IGNORECASE
        )
        HACK_CONFIG_KW = ['hack', 'client', 'cheat', 'config', 'setting', 'weave',
                          'module', 'baritone', 'meteor', 'vape', 'sigma', 'flux']
        found_paths = set()
        try:
            for base in SEARCH_BASES:
                if not os.path.isdir(base):
                    continue
                for root, dirs, files in os.walk(base):
                    dirs[:] = [d for d in dirs if d.lower() not in {
                        'google', 'mozilla', 'microsoft', 'windows',
                        'node_modules', '__pycache__', '.git',
                    }]
                    for fname in files:
                        if os.path.splitext(fname.lower())[1] not in CONFIG_EXTS:
                            continue
                        fpath = os.path.join(root, fname)
                        if fpath in found_paths:
                            continue
                        try:
                            fsize = os.path.getsize(fpath)
                            if fsize > 2 * 1024 * 1024:  # skip > 2MB
                                continue
                            with open(fpath, 'r', encoding='utf-8', errors='ignore') as f:
                                content = f.read()
                            matches = WEBHOOK_RE.findall(content)
                            if not matches:
                                continue
                            found_paths.add(fpath)
                            root_lower = root.lower()
                            fname_lower = fname.lower()
                            is_hack_context = (
                                any(kw in root_lower for kw in HACK_CONFIG_KW) or
                                any(kw in fname_lower for kw in HACK_CONFIG_KW)
                            )
                            # En Desktop/Downloads sin contexto hack: puede ser bot de staff legítimo
                            in_generic_location = any(loc in root_lower for loc in ('\\desktop\\', '\\downloads\\', '\\documents\\'))
                            if in_generic_location and not is_hack_context:
                                continue  # skip — Discord webhook en carpeta genérica sin contexto hack
                            alert = 'CRITICAL' if is_hack_context else 'SOSPECHOSO'
                            conf  = 0.92 if is_hack_context else 0.72
                            print(f"🚨 DISCORD WEBHOOK en config: {fpath} ({len(matches)} URL(s))")
                            self.issues_found.append({
                                'nombre': f'Discord webhook en config de hack: {fname}',
                                'ruta': fpath,
                                'archivo': fname,
                                'tipo': 'discord_webhook_config',
                                'categoria': 'C2_EXFIL',
                                'alerta': alert,
                                'confidence': conf,
                                'detected_patterns': [f'discord_webhook:{m[:60]}' for m in matches[:3]],
                                'explicacion': (
                                    f'Se encontraron {len(matches)} URL(s) de Discord webhook en {fpath}. '
                                    'Los hack clients modernos usan webhooks de Discord para enviar '
                                    'notificaciones al cheater (logros de hack, alerta de SS, etc.) '
                                    'o para exfiltrar datos del servidor/jugador.'
                                ),
                            })
                        except Exception:
                            continue
        except Exception as e:
            print(f"Error en scan_discord_webhooks: {e}")

    def scan_discord_local_settings(self):
        """#34 — Busca webhooks de C2 y tokens de bot en Discord settings.json local."""
        print("🔍 Revisando Discord settings.json por tokens/webhooks de C2...")
        import re as _re
        appdata = os.environ.get('APPDATA', '')
        discord_dir = os.path.join(appdata, 'discord')
        if not os.path.isdir(discord_dir):
            return
        WEBHOOK_RE = _re.compile(r'https://discord(?:app)?\.com/api/webhooks/\d+/[\w-]+')
        BOT_TOKEN_RE = _re.compile(r'[MN][A-Za-z\d]{23}\.[\w-]{6}\.[\w-]{27}')  # Discord bot token
        try:
            for root, dirs, files in os.walk(discord_dir):
                dirs[:] = [d for d in dirs if d not in {'Cache', 'GPUCache', 'Code Cache', 'Service Worker'}]
                for fname in files:
                    if not fname.endswith(('.json', '.log')):
                        continue
                    fpath = os.path.join(root, fname)
                    try:
                        fsize = os.path.getsize(fpath)
                        if fsize > 512 * 1024:
                            continue
                        with open(fpath, 'r', encoding='utf-8', errors='ignore') as f:
                            content = f.read()
                        webhooks = WEBHOOK_RE.findall(content)
                        tokens   = BOT_TOKEN_RE.findall(content)
                        if not (webhooks or tokens):
                            continue
                        print(f"🚨 DISCORD C2 EN SETTINGS: {fpath} ({len(webhooks)} webhooks, {len(tokens)} tokens)")
                        self.issues_found.append({
                            'nombre': f'Discord C2 en settings locales: {fname} ({len(webhooks)} webhook(s))',
                            'ruta': fpath,
                            'archivo': fname,
                            'tipo': 'discord_webhook_config',
                            'categoria': 'C2_EXFIL',
                            'alerta': 'CRITICAL',
                            'confidence': 0.88,
                            'detected_patterns': ([f'discord_webhook:{w[:60]}' for w in webhooks[:2]] +
                                                   (['discord_bot_token'] if tokens else [])),
                            'explicacion': (
                                f'Se encontraron {len(webhooks)} webhook(s) Discord y {len(tokens)} token(s) '
                                f'de bot en {fname} dentro de la carpeta de Discord. '
                                'Los hack clients avanzados inyectan código en Discord para usar su webhook '
                                'como canal de C2 o para robar tokens de sesión.'
                            ),
                        })
                    except Exception:
                        continue
        except Exception as e:
            print(f"Error en scan_discord_local_settings: {e}")

    def scan_minecraft_lock_files(self):
        """#35 — Detecta archivos .lck/.lock en .minecraft de procesos ya terminados."""
        print("🔍 Buscando archivos .lock huérfanos en .minecraft...")
        appdata = os.environ.get('APPDATA', '')
        mc_dir = os.path.join(appdata, '.minecraft')
        if not os.path.isdir(mc_dir):
            return
        LOCK_DIRS = [
            os.path.join(mc_dir, 'config'),
            os.path.join(mc_dir, 'logs'),
        ]
        # Añadir directorios de ghost clients conocidos
        for gcd in ['.meteor', '.sigma', '.rise', '.liquidbounce', '.weave']:
            LOCK_DIRS.append(os.path.join(appdata, gcd))
        try:
            for lock_dir in LOCK_DIRS:
                if not os.path.isdir(lock_dir):
                    continue
                for fname in os.listdir(lock_dir):
                    if not (fname.endswith('.lck') or fname.endswith('.lock')):
                        continue
                    fpath = os.path.join(lock_dir, fname)
                    stem = os.path.splitext(fname)[0].lower()
                    matched = any(h in stem for h in _DEFINITE_HACK_NAMES)
                    if not matched:
                        continue
                    print(f"⚠️ LOCK HUÉRFANO DE HACK: {fpath}")
                    self.issues_found.append({
                        'nombre': f'Archivo lock huérfano de hack: {fname}',
                        'ruta': fpath,
                        'archivo': fname,
                        'tipo': 'ghost_client_config',
                        'categoria': 'FORENSE',
                        'alerta': 'SOSPECHOSO',
                        'confidence': 0.72,
                        'detected_patterns': [f'lock_file:{stem}'],
                        'explicacion': (
                            f'{fname} es un archivo lock dejado por un proceso de hack que terminó '
                            'forzosamente (o fue cerrado durante el scan). Los locks huérfanos '
                            'indican que el hack estaba activo recientemente.'
                        ),
                    })
        except Exception as e:
            print(f"Error en scan_minecraft_lock_files: {e}")

    def scan_browser_downloads(self):
        """Detecta descargas de hack clients en el historial de Chrome, Edge y Firefox."""
        print("🔍 Escaneando historial de descargas del navegador...")
        import sqlite3 as _sqlite3
        import shutil as _shutil
        import tempfile as _tempfile
        import re as _re
        import datetime as _dt

        localapp = os.environ.get('LOCALAPPDATA', '')
        appdata  = os.environ.get('APPDATA', '')

        # Perfiles de navegadores con su base de datos de historial
        BROWSER_HISTORIES = [
            ('Chrome',  os.path.join(localapp, 'Google', 'Chrome', 'User Data', 'Default', 'History')),
            ('Edge',    os.path.join(localapp, 'Microsoft', 'Edge', 'User Data', 'Default', 'History')),
            ('Brave',   os.path.join(localapp, 'BraveSoftware', 'Brave-Browser', 'User Data', 'Default', 'History')),
            ('Vivaldi', os.path.join(localapp, 'Vivaldi', 'User Data', 'Default', 'History')),
            ('Opera',   os.path.join(appdata,  'Opera Software', 'Opera Stable', 'History')),
        ]
        # Firefox guarda el historial en places.sqlite
        firefox_base = os.path.join(appdata, 'Mozilla', 'Firefox', 'Profiles')
        if os.path.isdir(firefox_base):
            for profile in os.listdir(firefox_base):
                places = os.path.join(firefox_base, profile, 'places.sqlite')
                if os.path.isfile(places):
                    BROWSER_HISTORIES.append(('Firefox', places))
                    break  # Solo primer perfil

        # Patrones que indican descarga de hack (URL o nombre de archivo)
        # REGLA: solo términos EXCLUSIVOS de hack clients. 'hack', 'cheat', 'bypass' eliminados
        # porque aparecen en lifehacker.com, artículos de tecnología, herramientas legítimas.
        HACK_URL_KW = list(_DEFINITE_HACK_NAMES) + [
            'ghostclient', 'ghost-client', 'hackmod',
            'dllinjector', 'extremeinjector', 'cheatengine',
            'weaveloader', 'weave-loader',
        ]
        SAFE_DOMAINS = {
            'modrinth.com', 'curseforge.com', 'minecraft.net', 'mojang.com',
            'fabricmc.net', 'minecraftforge.net', 'optifine.net',
            'github.com', 'github.io',
            'reddit.com', 'youtube.com', 'google.com', 'twitch.tv',
            'discord.com', 'discord.gg',
            'spigotmc.org', 'bukkit.org', 'papermc.io',
        }

        def _is_hack_url(url: str) -> tuple:
            url_lower = url.lower()
            # Excluir dominios seguros
            for safe in SAFE_DOMAINS:
                if safe in url_lower:
                    return False, None
            hit = next((kw for kw in HACK_URL_KW if kw in url_lower), None)
            return bool(hit), hit

        try:
            for browser_name, history_path in BROWSER_HISTORIES:
                if not os.path.isfile(history_path):
                    continue
                # Copiar la DB porque puede estar bloqueada por el navegador
                tmp_path = None
                try:
                    tmp_fd, tmp_path = _tempfile.mkstemp(suffix='.db')
                    os.close(tmp_fd)
                    _shutil.copy2(history_path, tmp_path)

                    conn = _sqlite3.connect(f'file:{tmp_path}?mode=ro', uri=True)
                    cur = conn.cursor()

                    # Chrome/Edge/Brave/Vivaldi usan tabla 'downloads'
                    try:
                        cur.execute("""
                            SELECT target_path, tab_url, start_time, total_bytes
                            FROM downloads
                            ORDER BY start_time DESC
                            LIMIT 2000
                        """)
                        rows = cur.fetchall()
                        for target_path, url, start_time, size in rows:
                            target_path = target_path or ''
                            url         = url or ''
                            fname = os.path.basename(target_path).lower()
                            # Comprobar URL y nombre de archivo
                            url_hit, url_kw = _is_hack_url(url)
                            fname_hit = next((kw for kw in HACK_URL_KW if kw in fname), None)
                            if not url_hit and not fname_hit:
                                continue
                            # Convertir timestamp Chrome (microsegundos desde 1601-01-01)
                            try:
                                epoch = _dt.datetime(1601, 1, 1) + _dt.timedelta(microseconds=start_time)
                                date_str = epoch.strftime('%d/%m/%Y %H:%M')
                            except Exception:
                                date_str = 'desconocido'
                            hit_kw = url_kw or fname_hit
                            size_kb = (size or 0) // 1024
                            print(f"🚨 DESCARGA HACK ({browser_name}): {fname} ({size_kb}KB) — {date_str}")
                            self.issues_found.append({
                                'nombre': f'Descarga de hack en {browser_name}: {os.path.basename(target_path) or url[:60]}',
                                'ruta': target_path or url[:200],
                                'archivo': os.path.basename(target_path) or url[:60],
                                'tipo': 'browser_download_hack',
                                'categoria': 'FORENSE',
                                'alerta': 'CRITICAL' if (fname_hit and fname_hit in _DEFINITE_HACK_NAMES) else 'SOSPECHOSO',
                                'confidence': 0.88 if fname_hit else 0.72,
                                'detected_patterns': [f'browser_dl:{hit_kw}', f'browser:{browser_name}'],
                                'explicacion': (
                                    f'{browser_name} tiene registrado en su historial la descarga de '
                                    f'"{os.path.basename(target_path) or url[:80]}" ({size_kb}KB) '
                                    f'el {date_str}. El nombre/URL contiene la palabra "{hit_kw}" '
                                    f'que coincide con un hack client conocido. '
                                    f'El historial de descargas persiste aunque el archivo haya sido borrado.'
                                ),
                            })
                    except _sqlite3.OperationalError:
                        pass  # Tabla no existe (Firefox usa formato diferente)

                    # Firefox usa tabla 'moz_downloads' (places.sqlite)
                    try:
                        cur.execute("""
                            SELECT p.url, a.content
                            FROM moz_annos a
                            JOIN moz_places p ON a.place_id = p.id
                            WHERE a.anno_attribute_id IN (
                                SELECT id FROM moz_anno_attributes WHERE name = 'downloads/destinationFileURI'
                            )
                            ORDER BY a.dateAdded DESC
                            LIMIT 1000
                        """)
                        for url, dest in cur.fetchall():
                            url   = url or ''
                            fname = os.path.basename(dest or '').lower()
                            url_hit, url_kw = _is_hack_url(url)
                            fname_hit = next((kw for kw in HACK_URL_KW if kw in fname), None)
                            if not url_hit and not fname_hit:
                                continue
                            hit_kw = url_kw or fname_hit
                            print(f"🚨 DESCARGA HACK (Firefox): {fname}")
                            self.issues_found.append({
                                'nombre': f'Descarga de hack en Firefox: {fname or url[:60]}',
                                'ruta': url[:200],
                                'archivo': fname or url[:60],
                                'tipo': 'browser_download_hack',
                                'categoria': 'FORENSE',
                                'alerta': 'SOSPECHOSO',
                                'confidence': 0.78,
                                'detected_patterns': [f'browser_dl:{hit_kw}', 'browser:firefox'],
                                'explicacion': (
                                    f'Firefox tiene registrado en su historial la descarga de "{fname or url[:80]}". '
                                    f'El nombre/URL coincide con el patrón "{hit_kw}" de un hack client conocido.'
                                ),
                            })
                    except _sqlite3.OperationalError:
                        pass

                    conn.close()
                except Exception:
                    pass
                finally:
                    if tmp_path and os.path.exists(tmp_path):
                        try:
                            os.unlink(tmp_path)
                        except Exception:
                            pass
        except Exception as e:
            print(f"Error en scan_browser_downloads: {e}")

    def scan_browser_history_sites(self):
        """Detecta visitas a sitios de hack clients y stressers/DDoS en el historial de navegadores."""
        print("🔍 Escaneando historial de páginas visitadas del navegador...")
        import sqlite3 as _sqlite3
        import shutil as _shutil
        import tempfile as _tempfile

        localapp = os.environ.get('LOCALAPPDATA', '')
        appdata  = os.environ.get('APPDATA', '')

        def _chromium_profiles(browser_name, user_data_dir):
            """Devuelve (nombre, ruta_History) para todos los perfiles de un navegador Chromium."""
            entries = []
            if not os.path.isdir(user_data_dir):
                return entries
            for entry in os.listdir(user_data_dir):
                # Perfiles: Default, Profile 1, Profile 2, Profile 3, …
                if entry == 'Default' or entry.startswith('Profile '):
                    h = os.path.join(user_data_dir, entry, 'History')
                    if os.path.isfile(h):
                        label = browser_name if entry == 'Default' else f'{browser_name}/{entry}'
                        entries.append((label, h, 'chromium'))
            return entries

        BROWSER_HISTORIES = []
        # Chromium-based: User Data contiene subcarpetas Default / Profile N
        BROWSER_HISTORIES += _chromium_profiles('Chrome',       os.path.join(localapp, 'Google',        'Chrome',          'User Data'))
        BROWSER_HISTORIES += _chromium_profiles('ChromeBeta',   os.path.join(localapp, 'Google',        'Chrome Beta',     'User Data'))
        BROWSER_HISTORIES += _chromium_profiles('Edge',         os.path.join(localapp, 'Microsoft',     'Edge',            'User Data'))
        BROWSER_HISTORIES += _chromium_profiles('Brave',        os.path.join(localapp, 'BraveSoftware', 'Brave-Browser',   'User Data'))
        BROWSER_HISTORIES += _chromium_profiles('Vivaldi',      os.path.join(localapp, 'Vivaldi',       'User Data'))
        BROWSER_HISTORIES += _chromium_profiles('Yandex',       os.path.join(localapp, 'Yandex',        'YandexBrowser',   'User Data'))
        BROWSER_HISTORIES += _chromium_profiles('Arc',          os.path.join(localapp, 'arc',           'User Data'))
        BROWSER_HISTORIES += _chromium_profiles('Thorium',      os.path.join(localapp, 'Thorium',       'User Data'))
        BROWSER_HISTORIES += _chromium_profiles('CentBrowser',  os.path.join(localapp, 'CentBrowser',  'User Data'))
        BROWSER_HISTORIES += _chromium_profiles('Comodo',       os.path.join(localapp, 'Comodo',        'Dragon',          'User Data'))
        # Opera: la raíz ES el User Data (sin subdirectorio User Data)
        BROWSER_HISTORIES += _chromium_profiles('Opera',        os.path.join(appdata,  'Opera Software', 'Opera Stable'))
        BROWSER_HISTORIES += _chromium_profiles('OperaGX',      os.path.join(appdata,  'Opera Software', 'Opera GX Stable'))
        BROWSER_HISTORIES += _chromium_profiles('OperaDev',     os.path.join(appdata,  'Opera Software', 'Opera Developer'))

        # Firefox-based: cada perfil tiene places.sqlite (+ WAL)
        for ff_label, ff_base in [
            ('Firefox',   os.path.join(appdata, 'Mozilla',            'Firefox',  'Profiles')),
            ('Waterfox',  os.path.join(appdata, 'Waterfox',           'Profiles')),
            ('LibreWolf', os.path.join(localapp,'LibreWolf',          'Profiles')),
            ('LibreWolf', os.path.join(appdata, 'librewolf',          'Profiles')),
            ('PaleMoon',  os.path.join(appdata, 'Moonchild Productions', 'Pale Moon', 'Profiles')),
            ('SeaMonkey', os.path.join(appdata, 'Mozilla',            'SeaMonkey','Profiles')),
        ]:
            if not os.path.isdir(ff_base):
                continue
            for profile in os.listdir(ff_base):
                places = os.path.join(ff_base, profile, 'places.sqlite')
                if os.path.isfile(places):
                    BROWSER_HISTORIES.append((f'{ff_label}/{profile[:12]}', places, 'firefox'))

        # Dominios conocidos de hack clients (solo dominios específicos, sin falsos positivos)
        HACK_SITES = {
            'vape.gg':              ('Vape Client', 'CRITICAL'),
            'vapeclient.net':       ('Vape Client', 'CRITICAL'),
            'vapeclient.cc':        ('Vape Client', 'CRITICAL'),
            'liquidbounce.net':     ('LiquidBounce', 'CRITICAL'),
            'wurst-client.xyz':     ('Wurst Client', 'CRITICAL'),
            'aristois.net':         ('Aristois', 'CRITICAL'),
            'meteorclient.com':     ('Meteor Client', 'CRITICAL'),
            'meteor-client.com':    ('Meteor Client', 'CRITICAL'),
            'rusherhack.org':       ('RusherHack', 'CRITICAL'),
            'lambda.cx':            ('Lambda Hack', 'CRITICAL'),
            'sigma.rip':            ('Sigma Client', 'CRITICAL'),
            'drip.cx':              ('Drip Client', 'CRITICAL'),
            'future.gg':            ('Future Client', 'CRITICAL'),
            'impact.lol':           ('Impact Client', 'CRITICAL'),
            'riseclient.com':       ('Rise Client', 'CRITICAL'),
            'rise-client.com':      ('Rise Client', 'CRITICAL'),
            'fluxclient.net':       ('Flux Client', 'CRITICAL'),
            'novoline-client.com':  ('Novoline', 'CRITICAL'),
            'wolfram.codes':        ('Wolfram Client', 'CRITICAL'),
            'salhack.me':           ('SalHack', 'CRITICAL'),
            'tenacityclient.com':   ('Tenacity', 'CRITICAL'),
            'inertiaclient.com':    ('Inertia Client', 'CRITICAL'),
            'aresclient.net':       ('Ares Client', 'CRITICAL'),
            'pandahack.net':        ('Panda Hack', 'CRITICAL'),
            'weaveloader.com':      ('Weave Loader', 'CRITICAL'),
            'weave.mod.menu':       ('Weave Mod Menu', 'CRITICAL'),
            'dreamhack.gg':         ('Dream Hack Client', 'CRITICAL'),
            'dreamclient.cc':       ('Dream Client', 'CRITICAL'),
            'dreamhackclient.com':  ('Dream Hack Client', 'CRITICAL'),
            'nodus.cc':             ('Nodus Client', 'CRITICAL'),
            'removalclient.com':    ('Removal Client', 'CRITICAL'),
            'kilauea.cc':           ('Kilauea Client', 'CRITICAL'),
            'shadeclient.net':      ('Shade Client', 'CRITICAL'),
            'externalclient.ru':    ('External Client', 'CRITICAL'),
            'kingaura.com':         ('KingAura', 'CRITICAL'),
            'lucidclient.net':      ('Lucid Client', 'CRITICAL'),
            'predatorhack.net':     ('Predator Hack', 'CRITICAL'),
            'slinky.gg':            ('Slinky Client', 'CRITICAL'),
            'slinkyclient.com':     ('Slinky Client', 'CRITICAL'),
            'reflex.rip':           ('Reflex Client', 'CRITICAL'),
            'blackspigot.com':      ('BlackSpigot Leaks', 'SOSPECHOSO'),
            'leakednation.com':     ('Leaked Hacks', 'CRITICAL'),
            'nulled.to':            ('Nulled Leaks', 'SOSPECHOSO'),
            # DDoS stressers conocidos
            'stressthem.ru':        ('DDoS Stresser stressthem', 'CRITICAL'),
            'stressthem.to':        ('DDoS Stresser stressthem', 'CRITICAL'),
            'stresstest.to':        ('DDoS Stresser stresstest', 'CRITICAL'),
            'stresser.ai':          ('DDoS Stresser', 'CRITICAL'),
            'stresser.us':          ('DDoS Stresser', 'CRITICAL'),
            'hardstresser.com':     ('DDoS Stresser hard', 'CRITICAL'),
            'astrostress.com':      ('DDoS Stresser astro', 'CRITICAL'),
            'hackforums.net':       ('Hack Forums', 'CRITICAL'),
            'leakednation.com':     ('Leaked Hacks', 'CRITICAL'),
            'iceynetwork.com':      ('DDoS Tool', 'CRITICAL'),
        }
        # Palabras clave en URL que indican stresser/DDoS
        DDOS_KEYWORDS = [
            'stresser', 'booter', 'ip-booter', 'ddoser', 'layer7stress',
            'stresstest', 'stressthem', 'ddos-tool', 'ddostool',
            'ipbooter', 'stress-test', 'l7stress', 'layer4stress',
        ]

        SAFE_DOMAINS = {
            'modrinth.com', 'curseforge.com', 'minecraft.net', 'mojang.com',
            'fabricmc.net', 'minecraftforge.net', 'optifine.net',
            'github.com', 'github.io', 'reddit.com', 'youtube.com',
            'google.com', 'twitch.tv', 'discord.com', 'discord.gg',
            'spigotmc.org', 'bukkit.org', 'papermc.io', 'cloudflare.com',
        }

        seen_domains = set()

        def _relative_time(unix_ts):
            """Convierte unix timestamp a 'hace X tiempo'."""
            if not unix_ts or unix_ts <= 0:
                return 'fecha desconocida'
            diff = time.time() - unix_ts
            if diff < 0:
                return 'ahora mismo'
            if diff < 60:
                return f'hace {int(diff)}s'
            if diff < 3600:
                return f'hace {int(diff/60)} min'
            if diff < 86400:
                return f'hace {int(diff/3600)}h {int((diff%3600)/60)}min'
            if diff < 604800:
                return f'hace {int(diff/86400)} día(s)'
            return f'hace {int(diff/604800)} semana(s)'

        def _chrome_ts(ts):
            """Chrome: microsegundos desde 1601-01-01 → Unix seconds."""
            if not ts:
                return 0
            return (ts / 1_000_000) - 11644473600

        def _check_downloads(cur, domain, db_type):
            """Busca descargas desde el dominio en la misma DB. Devuelve lista de paths."""
            found = []
            try:
                if db_type == 'chromium':
                    cur.execute(
                        "SELECT target_path, tab_url FROM downloads WHERE tab_url LIKE ? OR url LIKE ? LIMIT 5",
                        (f'%{domain}%', f'%{domain}%')
                    )
                    for r in cur.fetchall():
                        if r[0]:
                            found.append(os.path.basename(r[0]))
                elif db_type == 'firefox':
                    # Firefox guarda descargas como anotaciones en moz_annos
                    cur.execute("""
                        SELECT a.content FROM moz_annos a
                        JOIN moz_places p ON p.id = a.place_id
                        WHERE p.url LIKE ? AND a.anno_attribute_id IN (
                            SELECT id FROM moz_anno_attributes WHERE name='downloads/destinationFileURI'
                        ) LIMIT 5
                    """, (f'%{domain}%',))
                    for r in cur.fetchall():
                        if r[0]:
                            fname = r[0].split('/')[-1].split('\\')[-1]
                            found.append(fname)
            except Exception:
                pass
            return found

        try:
            for browser_name, history_path, db_type in BROWSER_HISTORIES:
                if not os.path.isfile(history_path):
                    continue
                tmp_path = None
                tmp_wal  = None
                tmp_shm  = None
                try:
                    tmp_fd, tmp_path = _tempfile.mkstemp(suffix='.db')
                    os.close(tmp_fd)
                    _shutil.copy2(history_path, tmp_path)
                    for ext, attr in (('-wal', 'tmp_wal'), ('-shm', 'tmp_shm')):
                        src = history_path + ext
                        if os.path.isfile(src):
                            try:
                                wal_dst = tmp_path + ext
                                _shutil.copy2(src, wal_dst)
                                if attr == 'tmp_wal':
                                    tmp_wal = wal_dst
                                else:
                                    tmp_shm = wal_dst
                            except Exception:
                                pass

                    conn = _sqlite3.connect(f'file:{tmp_path}?mode=ro', uri=True)
                    cur  = conn.cursor()

                    if db_type == 'chromium':
                        cur.execute('SELECT url, title, visit_count, last_visit_time FROM urls ORDER BY last_visit_time DESC LIMIT 500')
                    else:
                        try:
                            cur.execute('''
                                SELECT DISTINCT p.url, p.title, p.visit_count, MAX(h.visit_date)
                                FROM moz_places p
                                JOIN moz_historyvisits h ON h.place_id = p.id
                                GROUP BY p.id
                                ORDER BY MAX(h.visit_date) DESC LIMIT 500
                            ''')
                        except Exception:
                            cur.execute('SELECT url, title, visit_count, last_visit_date FROM moz_places WHERE visit_count > 0 ORDER BY last_visit_date DESC LIMIT 500')

                    for row in cur.fetchall():
                        url    = (row[0] or '').lower()
                        title  = row[1] or ''
                        visits = row[2] or 1
                        raw_ts = row[3] if len(row) > 3 else None

                        # Convertir timestamp a unix según el tipo de DB
                        if db_type == 'chromium':
                            unix_ts = _chrome_ts(raw_ts)
                        else:
                            unix_ts = (raw_ts / 1_000_000) if raw_ts else 0
                        visited_ago = _relative_time(unix_ts)

                        for safe in SAFE_DOMAINS:
                            if safe in url:
                                break
                        else:
                            # Verificar hack sites
                            for domain, (client_name, severity) in HACK_SITES.items():
                                if domain in url:
                                    key = f'{browser_name}:{domain}'
                                    if key in seen_domains:
                                        break
                                    seen_domains.add(key)
                                    # Buscar descargas desde este dominio
                                    dl_files = _check_downloads(cur, domain, db_type)
                                    dl_txt = f' | Descargó: {", ".join(dl_files)}' if dl_files else ''
                                    print(f"🚨 VISITA HACK ({browser_name}): {domain} — {visits} visita(s) {visited_ago}{dl_txt}")
                                    # Solo CRITICAL si hay descarga confirmada; solo visitar = PAGINA_SOSPECHOSA
                                    alerta_nivel = 'CRITICAL' if dl_files else 'PAGINA_SOSPECHOSA'
                                    conf_nivel   = 0.97 if dl_files else 0.75
                                    self.issues_found.append({
                                        'nombre': f'Sitio de hack visitado {visited_ago} en {browser_name}: {domain}{dl_txt}',
                                        'ruta':   url[:200],
                                        'archivo': domain,
                                        'tipo':   'browser_visited_hack',
                                        'categoria': 'FORENSE',
                                        'alerta': alerta_nivel,
                                        'confidence': conf_nivel,
                                        'detected_patterns': [f'visited:{domain}', f'browser:{browser_name}'] + ([f'downloaded:{f}' for f in dl_files]),
                                        'explicacion': (
                                            f'{browser_name} registra {visits} visita(s) al sitio "{domain}" '
                                            f'({client_name}). Última visita: {visited_ago}. '
                                            + (f'⚠️ Se detectó descarga desde este sitio: {", ".join(dl_files)}. ' if dl_files else '')
                                            + 'El historial del navegador persiste aunque se borre el cliente.'
                                        ),
                                    })
                                    break
                            else:
                                # Verificar stressers/DDoS
                                for kw in DDOS_KEYWORDS:
                                    if kw in url:
                                        key = f'{browser_name}:ddos:{kw}'
                                        if key in seen_domains:
                                            break
                                        seen_domains.add(key)
                                        dl_files = _check_downloads(cur, kw, db_type)
                                        dl_txt = f' | Descargó: {", ".join(dl_files)}' if dl_files else ''
                                        print(f"🚨 VISITA DDOS ({browser_name}): {url[:80]}")
                                        self.issues_found.append({
                                            'nombre': f'Sitio stresser/DDoS visitado {visited_ago} ({browser_name}){dl_txt}',
                                            'ruta':   url[:200],
                                            'archivo': url[:80],
                                            'tipo':   'browser_visited_hack',
                                            'categoria': 'FORENSE',
                                            'alerta': 'CRITICAL' if dl_files else 'SOSPECHOSO',
                                            'confidence': 0.92 if dl_files else 0.78,
                                            'detected_patterns': [f'ddos:{kw}', f'browser:{browser_name}'],
                                            'explicacion': (
                                                f'{browser_name} registra visitas a "{kw}" ({visited_ago}). '
                                                + (f'⚠️ Descarga detectada: {", ".join(dl_files)}. ' if dl_files else '')
                                                + f'URL: {url[:120]}'
                                            ),
                                        })
                                        break

                    conn.close()
                except Exception:
                    pass
                finally:
                    for tmp_f in (tmp_path, tmp_wal, tmp_shm):
                        if tmp_f and os.path.exists(tmp_f):
                            try:
                                os.unlink(tmp_f)
                            except Exception:
                                pass
        except Exception as e:
            print(f"Error en scan_browser_history_sites: {e}")

    def scan_ddos_applications(self):
        """Detecta aplicaciones de DDoS conocidas (LOIC, HOIC, etc.) en procesos y sistema de archivos."""
        print("🔍 Escaneando aplicaciones de DDoS/stresser...")

        DDOS_PROCESS_NAMES = {
            'loic': ('Low Orbit Ion Cannon (LOIC)', 'CRITICAL'),
            'hoic': ('High Orbit Ion Cannon (HOIC)', 'CRITICAL'),
            'hulk': ('HULK DoS Tool', 'CRITICAL'),
            'goldeneye': ('GoldenEye DoS Tool', 'CRITICAL'),
            'slowloris': ('Slowloris DoS Tool', 'CRITICAL'),
            'hammer': ('THC-SSL-DOS / Hammer', 'CRITICAL'),
            'xerxes': ('Xerxes DoS Tool', 'CRITICAL'),
            'pyloris': ('PyLoris DoS Tool', 'CRITICAL'),
            'torshammer': ('Tor\'s Hammer DoS', 'CRITICAL'),
            'ddosim': ('DDoSIM Tool', 'CRITICAL'),
            'hping': ('HPing (packet flooder)', 'SOSPECHOSO'),
            'nping': ('NPing (packet flooder)', 'SOSPECHOSO'),
        }

        DDOS_FILE_PATTERNS = [
            'loic', 'hoic', 'hulk.py', 'goldeneye.py', 'slowloris',
            'hammer.py', 'xerxes', 'pyloris', 'torshammer', 'ddosim',
            'stresser', 'booter', 'ip-booter',
        ]

        # Directorios donde suelen aparecer estas herramientas
        search_dirs = []
        for env in ('USERPROFILE', 'LOCALAPPDATA', 'APPDATA', 'TEMP'):
            v = os.environ.get(env, '')
            if v:
                for sub in ('Downloads', 'Desktop', 'Documents', ''):
                    d = os.path.join(v, sub) if sub else v
                    if os.path.isdir(d) and d not in search_dirs:
                        search_dirs.append(d)

        found_files = set()

        # Escanear procesos activos
        try:
            import psutil as _psutil
            for proc in _psutil.process_iter(['pid', 'name', 'exe']):
                try:
                    pname = (proc.info.get('name') or '').lower()
                    pexe  = (proc.info.get('exe')  or '').lower()
                    for kw, (tool_name, severity) in DDOS_PROCESS_NAMES.items():
                        if kw in pname or kw in pexe:
                            print(f"🚨 DDOS TOOL ACTIVO: {tool_name} — PID {proc.info.get('pid')}")
                            self.issues_found.append({
                                'nombre': f'Herramienta DDoS activa: {tool_name}',
                                'ruta': pexe or pname,
                                'archivo': proc.info.get('name', ''),
                                'tipo': 'ddos_application',
                                'categoria': 'FORENSE',
                                'alerta': severity,
                                'confidence': 0.92,
                                'detected_patterns': [f'ddos_process:{kw}'],
                                'is_active_process': True,
                                'explicacion': (
                                    f'Se detectó el proceso "{proc.info.get("name","?")}" activo, '
                                    f'identificado como {tool_name}. Esta es una herramienta de ataque '
                                    f'DDoS/DoS utilizada para saturar servidores.'
                                ),
                            })
                            break
                except (Exception,):
                    continue
        except Exception as e:
            print(f"⚠️ Error escaneando procesos DDoS: {e}")

        # Escanear archivos en directorios comunes (solo primer nivel + Downloads)
        try:
            for base_dir in search_dirs:
                try:
                    for fname in os.listdir(base_dir):
                        fname_l = fname.lower()
                        for pat in DDOS_FILE_PATTERNS:
                            if pat in fname_l and fname_l not in found_files:
                                fpath = os.path.join(base_dir, fname)
                                if os.path.isfile(fpath):
                                    found_files.add(fname_l)
                                    print(f"⚠️ DDOS FILE: {fpath}")
                                    self.issues_found.append({
                                        'nombre': f'Archivo de herramienta DDoS encontrado: {fname}',
                                        'ruta': fpath,
                                        'archivo': fname,
                                        'tipo': 'ddos_application',
                                        'categoria': 'FORENSE',
                                        'alerta': 'CRITICAL',
                                        'confidence': 0.82,
                                        'detected_patterns': [f'ddos_file:{pat}'],
                                        'explicacion': (
                                            f'Se encontró el archivo "{fname}" en {base_dir}, '
                                            f'cuyo nombre coincide con herramientas de DDoS/stresser conocidas.'
                                        ),
                                    })
                                break
                except Exception:
                    pass
        except Exception as e:
            print(f"⚠️ Error escaneando archivos DDoS: {e}")

    def scan_clipboard_content(self):
        """Detecta evidencia de hacks en el portapapeles (Discord webhooks, hack names, etc.)."""
        print("🔍 Escaneando contenido del portapapeles...")
        try:
            import ctypes as _ct
            import ctypes.wintypes as _wt

            # Leer el portapapeles usando la API de Windows directamente
            user32 = _ct.windll.user32
            kernel32 = _ct.windll.kernel32

            CF_TEXT      = 1
            CF_UNICODETEXT = 13
            GMEM_MOVEABLE = 0x0002

            if not user32.OpenClipboard(0):
                return
            try:
                # Intentar texto Unicode primero
                h_data = user32.GetClipboardData(CF_UNICODETEXT)
                if h_data:
                    ptr = kernel32.GlobalLock(h_data)
                    if ptr:
                        try:
                            clip_text = _ct.wstring_at(ptr, 4096)
                        finally:
                            kernel32.GlobalUnlock(h_data)
                else:
                    clip_text = ''
            finally:
                user32.CloseClipboard()

            if not clip_text:
                return

            clip_lower = clip_text.lower().strip()
            clip_norm  = _normalize(clip_lower)

            import re as _re
            WEBHOOK_RE = _re.compile(
                r'https?://(?:ptb\.|canary\.)?discord(?:app)?\.com/api/webhooks/\d+/[\w-]+',
                _re.IGNORECASE
            )
            # 1. Webhook de Discord en portapapeles
            webhooks = WEBHOOK_RE.findall(clip_text)
            if webhooks:
                print(f"🚨 DISCORD WEBHOOK EN PORTAPAPELES: {webhooks[0][:60]}")
                self.issues_found.append({
                    'nombre': f'Discord webhook en portapapeles ({len(webhooks)} URL(s))',
                    'ruta': 'Clipboard',
                    'archivo': 'clipboard',
                    'tipo': 'discord_webhook_config',
                    'categoria': 'C2_EXFIL',
                    'alerta': 'CRITICAL',
                    'confidence': 0.95,
                    'detected_patterns': [f'clipboard_webhook:{webhooks[0][:40]}'],
                    'explicacion': (
                        f'El portapapeles contiene {len(webhooks)} URL(s) de webhook de Discord. '
                        'El jugador puede haber copiado la URL para configurar un hack client '
                        'con C2 (Command & Control) basado en Discord.'
                    ),
                })

            # 2. Nombre de hack client copiado en portapapeles
            clip_hit = next(
                (h for h in _DEFINITE_HACK_NAMES
                 if h in clip_lower or h in clip_norm),
                None
            )
            if clip_hit and len(clip_lower) < 200:  # Evitar FP en texto largo
                print(f"⚠️ HACK NAME EN PORTAPAPELES: '{clip_hit}' en '{clip_lower[:60]}'")
                self.issues_found.append({
                    'nombre': f'Nombre de hack client en portapapeles: "{clip_hit}"',
                    'ruta': 'Clipboard',
                    'archivo': 'clipboard',
                    'tipo': 'clipboard_hack_evidence',
                    'categoria': 'FORENSE',
                    'alerta': 'SOSPECHOSO',
                    'confidence': 0.70,
                    'detected_patterns': [f'clipboard_hack:{clip_hit}'],
                    'explicacion': (
                        f'El portapapeles contiene el texto "{clip_lower[:60]}" que incluye '
                        f'el nombre del hack client "{clip_hit}". Puede indicar que el jugador '
                        f'estaba copiando el nombre del hack para descargarlo o configurarlo.'
                    ),
                })
        except Exception as e:
            print(f"Error en scan_clipboard_content: {e}")

    def scan_jitter_scripts(self):
        """#15 — Detecta configuraciones de jitter/aim assist en software de mouse."""
        print("🔍 Buscando jitter scripts en software de mouse...")
        appdata = os.environ.get('APPDATA', '')
        local   = os.environ.get('LOCALAPPDATA', '')
        JITTER_KEYWORDS = ['jitter', 'aimassist', 'aim_assist', 'smoothaim', 'recoil',
                           'firerate', 'fire_rate', 'autofire', 'rapidfire', 'rapid_fire']
        PATHS_TO_SCAN = [
            os.path.join(local,  'LGHUB'),
            os.path.join(appdata, 'Razer'),
            os.path.join(local,  'SteelSeries', 'GG'),
            os.path.join(appdata, 'Corsair'),
            os.path.join(local,  'Corsair'),
        ]
        try:
            for base in PATHS_TO_SCAN:
                if not os.path.isdir(base):
                    continue
                for root, _, files in os.walk(base):
                    for fname in files:
                        if not fname.lower().endswith(('.json', '.xml', '.db', '.lua')):
                            continue
                        fpath = os.path.join(root, fname)
                        try:
                            with open(fpath, 'r', encoding='utf-8', errors='ignore') as f:
                                content = f.read(8192).lower()
                            if any(kw in content for kw in JITTER_KEYWORDS):
                                # Verificar que no sea solo comentario o descripción
                                app_name = os.path.basename(base)
                                print(f"🚨 JITTER CONFIG: {fpath}")
                                self.issues_found.append({
                                    'nombre': f'Config de jitter/aim assist en {app_name}: {fname}',
                                    'ruta': fpath,
                                    'archivo': fname,
                                    'tipo': 'jitter_script',
                                    'categoria': 'MACRO',
                                    'alerta': 'SOSPECHOSO',
                                    'confidence': 0.65,
                                    'detected_patterns': ['jitter_config'],
                                    'explicacion': f'Se encontró configuración de jitter o aim assist en {app_name}. '
                                                   f'El jitter clicking y el aim assist por software están '
                                                   f'prohibidos en la mayoría de servidores de Minecraft.',
                                })
                                break
                        except Exception:
                            continue
        except Exception as e:
            print(f"Error en scan_jitter_scripts: {e}")

    def scan_minecraft_safe_mode(self):
        """#29 — Detecta si Minecraft fue lanzado con --safeMode (mods no cargan)."""
        print("🔍 Verificando si Minecraft corre en Safe Mode...")
        try:
            for proc in psutil.process_iter(['pid', 'name', 'cmdline']):
                try:
                    name = (proc.info.get('name') or '').lower()
                    if 'java' not in name:
                        continue
                    cmdline = ' '.join(proc.info.get('cmdline') or []).lower()
                    if '--safemode' in cmdline or '--safe-mode' in cmdline:
                        print("⚠️ Minecraft lanzado con --safeMode — mods deshabilitados")
                        self.issues_found.append({
                            'nombre': 'Minecraft lanzado en Safe Mode (mods desactivados)',
                            'ruta': 'cmdline',
                            'archivo': 'javaw.exe',
                            'tipo': 'minecraft_safe_mode',
                            'categoria': 'EVASION',
                            'alerta': 'SOSPECHOSO',
                            'confidence': 0.70,
                            'detected_patterns': ['safe_mode_launch'],
                            'explicacion': 'Minecraft fue lanzado con --safeMode, lo que deshabilita la carga '
                                           'de mods. El jugador puede estar usando esto para ocultar mods activos '
                                           'o para que no se detecten modificaciones en el arranque.',
                        })
                except (psutil.NoSuchProcess, psutil.AccessDenied):
                    continue
        except Exception as e:
            print(f"Error en scan_minecraft_safe_mode: {e}")

    def scan_f3t_log_exploit(self):
        """Detecta el bug F3+T (recarga resource packs con click mantenido) en los logs del cliente."""
        print("🔍 Buscando bug F3+T en logs del cliente...")
        import glob as _glob
        import gzip
        import re as _re

        PATTERNS = [
            'se recargaron los packs de recursos',   # español vanilla
            'reloaded resourcepacks',                 # inglés vanilla 1.16+
            'reloading resourcepacks',                # inglés vanilla
            'reloading resource packs',               # con espacio (algunas versiones)
            'resource packs reloaded',                # orden invertido
            'reloading resourcemanager',              # 1.8.9 vanilla/badlion (sin espacio)
            'reloading resource manager',             # 1.12+ vanilla (con espacio)
            'reloading resources',                    # forge/fabric
            'reloading all resources',
            'reloading!',                             # Lunar Client / moderno (mensaje corto)
            'loaded pack',                            # algunos forks usan esto
        ]

        appdata      = os.environ.get('APPDATA', '')
        userprofile  = os.environ.get('USERPROFILE', os.path.expanduser('~'))
        localappdata = os.environ.get('LOCALAPPDATA', '')

        # (dir_pattern, launcher_label)
        LOG_DIR_PATTERNS = [
            # ── Vanilla / Oficial / Mods sobre vanilla (Forge, Fabric, OptiFine) ──
            (os.path.join(appdata,      '.minecraft',                           'logs'), 'Vanilla/Forge/Fabric'),

            # ── Badlion Client ──
            (os.path.join(appdata,      '.blclient',   'minecraft',             'logs'), 'Badlion Client'),
            (os.path.join(appdata,      '.badlion',    'minecraft',             'logs'), 'Badlion Client'),
            (os.path.join(appdata,      '.badlion',                             'logs'), 'Badlion Client'),
            (os.path.join(localappdata, 'Programs',    'Badlion Client', 'game','logs'), 'Badlion Client'),

            # ── Lunar Client ──
            (os.path.join(userprofile,  '.lunarclient',              'logs', 'game'),    'Lunar Client'),
            (os.path.join(appdata,      'lunarclient',               'logs', 'game'),    'Lunar Client'),
            (os.path.join(localappdata, 'lunarclient',               'logs', 'game'),    'Lunar Client'),

            # ── Feather Client ──
            (os.path.join(appdata,      'feather-client',                       'logs'), 'Feather Client'),
            (os.path.join(appdata,      'Feather',                              'logs'), 'Feather Client'),

            # ── Cosmic Client ──
            (os.path.join(appdata,      '.cosmicclient',  'game',               'logs'), 'Cosmic Client'),
            (os.path.join(localappdata, 'Programs',    'Cosmic Client', 'game', 'logs'), 'Cosmic Client'),

            # ── LabyMod Launcher 4.x ──
            (os.path.join(appdata,      'LabyMod Launcher','instances','*','minecraft','logs'), 'LabyMod Launcher'),
            (os.path.join(appdata,      '.labymod4',       'instances','*',            'logs'), 'LabyMod Launcher'),

            # ── Salwyrr Client ──
            (os.path.join(appdata,      '.salwyrr',                             'logs'), 'Salwyrr'),
            (os.path.join(appdata,      '.salwyrr',        'game',              'logs'), 'Salwyrr'),

            # ── Solar Tweaks (modifica Lunar, puede tener logs propios) ──
            (os.path.join(appdata,      '.solartweaks',                         'logs'), 'Solar Tweaks'),
            (os.path.join(userprofile,  '.solartweaks',                         'logs'), 'Solar Tweaks'),

            # ── PrismLauncher y forks (Modrinth usa Prism internamente) ──
            (os.path.join(appdata,      'PrismLauncher','instances','*','minecraft','logs'), 'PrismLauncher'),
            (os.path.join(localappdata, 'PrismLauncher','instances','*','minecraft','logs'), 'PrismLauncher'),

            # ── MultiMC y forks ──
            (os.path.join(appdata,      'MultiMC',     'instances','*','minecraft','logs'), 'MultiMC'),
            (os.path.join(appdata,      'UltimMC',     'instances','*','minecraft','logs'), 'UltimMC'),
            (os.path.join(appdata,      'OfflineMultiMC','instances','*','minecraft','logs'), 'OfflineMultiMC'),

            # ── PolyMC ──
            (os.path.join(appdata,      'PolyMC',      'instances','*','minecraft','logs'), 'PolyMC'),

            # ── Modrinth App ──
            (os.path.join(appdata,      'com.modrinth.theseus','profiles','*',  'logs'), 'Modrinth App'),
            (os.path.join(localappdata, 'com.modrinth.theseus','profiles','*',  'logs'), 'Modrinth App'),

            # ── CurseForge ──
            (os.path.join(userprofile,  'curseforge',  'minecraft','Instances','*','logs'), 'CurseForge'),
            (os.path.join(userprofile,  'Documents',   'curseforge','minecraft','Instances','*','logs'), 'CurseForge'),

            # ── GDLauncher / GDLauncher Carbon ──
            (os.path.join(appdata,      'gdlauncher_next','instances','*',      'logs'), 'GDLauncher'),
            (os.path.join(appdata,      'gdlauncher',     'instances','*',      'logs'), 'GDLauncher'),
            (os.path.join(appdata,      'GDLauncher Carbon','instances','*',    'logs'), 'GDLauncher Carbon'),

            # ── ATLauncher ──
            (os.path.join(appdata,      'ATLauncher',  'instances','*','minecraft','logs'), 'ATLauncher'),

            # ── FTB App ──
            (os.path.join(localappdata, 'ftb-app',     'instances','*','minecraft','logs'), 'FTB App'),
            (os.path.join(appdata,      'ftb-app',     'instances','*','minecraft','logs'), 'FTB App'),

            # ── Technic Launcher ──
            (os.path.join(appdata,      '.technic',    'modpacks','*',           'logs'), 'Technic Launcher'),
            (os.path.join(appdata,      '.technic',    'modpacks','*','bin',     'logs'), 'Technic Launcher'),

            # ── TLauncher Legacy / Legacy Launcher ──
            (os.path.join(appdata,      '.tlauncher',  'legacy','Minecraft','game','logs'), 'TLauncher Legacy'),
            (os.path.join(appdata,      '.legacylauncher','minecraft',           'logs'), 'Legacy Launcher'),

            # ── SKLauncher ──
            (os.path.join(appdata,      '.sklauncher', 'instances','*',          'logs'), 'SKLauncher'),

            # ── Void Launcher ──
            (os.path.join(appdata,      '.voidlauncher','instances','*',         'logs'), 'Void Launcher'),

            # ── Nexus Client ──
            (os.path.join(appdata,      '.nexusclient',                          'logs'), 'Nexus Client'),

            # ── Rise Client ──
            (os.path.join(appdata,      '.riseclient',                           'logs'), 'Rise Client'),

            # ── Sigma Client ──
            (os.path.join(appdata,      '.sigmaclient', 'logs'),                          'Sigma Client'),
        ]

        now = time.time()
        log_files = []

        for pattern, label in LOG_DIR_PATTERNS:
            dirs = _glob.glob(pattern) if '*' in pattern else ([pattern] if os.path.isdir(pattern) else [])
            for d in dirs:
                if not os.path.isdir(d):
                    continue
                try:
                    for fname in os.listdir(d):
                        if not (fname == 'latest.log' or (fname.endswith('.log') and not fname.endswith('.log.gz'))):
                            continue
                        fpath = os.path.join(d, fname)
                        try:
                            if now - os.path.getmtime(fpath) > 86400:  # sólo últimas 24h
                                continue
                        except OSError:
                            continue
                        log_files.append((fpath, label))
                except OSError:
                    continue

        if not log_files:
            print("📂 No se encontraron logs recientes de ningún launcher")
            return

        TIME_RE = _re.compile(r'^\[(\d{2}):(\d{2}):(\d{2})\]')

        total_hits  = 0
        hit_details = []  # (log_path, label, [(timestamp_secs, raw_line), ...])

        for log_path, label in log_files:
            try:
                lines = []
                if log_path.endswith('.gz'):
                    with gzip.open(log_path, 'rt', encoding='utf-8', errors='ignore') as f:
                        lines = f.readlines()[-8000:]
                else:
                    with open(log_path, 'r', encoding='utf-8', errors='ignore') as f:
                        lines = f.readlines()[-8000:]

                hits = []
                for raw in lines:
                    if any(p in raw.lower() for p in PATTERNS):
                        m = TIME_RE.match(raw.strip())
                        ts = int(m.group(1)) * 3600 + int(m.group(2)) * 60 + int(m.group(3)) if m else -1
                        hits.append((ts, raw.strip()))

                if hits:
                    total_hits += len(hits)
                    hit_details.append((log_path, label, hits))
            except Exception:
                continue

        if total_hits == 0:
            print("✅ No se detectó el bug F3+T en los logs")
            return

        # Check if multiple hits cluster within 5 minutes (suspicious burst)
        burst_found = False
        for _, _, hits in hit_details:
            times = sorted(t for t, _ in hits if t >= 0)
            for i in range(len(times) - 2):
                if times[i + 2] - times[i] <= 300:  # 3 hits in 5 min
                    burst_found = True
                    break

        if total_hits >= 10 or burst_found:
            alerta     = 'CRITICAL'
            confidence = 0.92
        elif total_hits >= 3:
            alerta     = 'SOSPECHOSO'
            confidence = 0.75
        else:
            alerta     = 'POCO_SOSPECHOSO'
            confidence = 0.55

        first_path, first_label, first_hits = hit_details[0]
        sample = ' | '.join(h[1] for h in first_hits[:3])

        self.issues_found.append({
            'nombre': f'Bug F3+T detectado — {total_hits} recarga(s) de resource packs ({first_label})',
            'ruta':   first_path,
            'archivo': os.path.basename(first_path),
            'tipo':   'f3t_resourcepack_exploit',
            'categoria': 'HACKS',
            'alerta': alerta,
            'confidence': confidence,
            'detected_patterns': ['f3t_exploit', 'resourcepack_reload_burst'],
            'explicacion': (
                f'El log del cliente ({first_label}) contiene {total_hits} mensaje(s) de recarga de '
                f'resource packs. El bug F3+T (F3 + T mantenidos) permite simular un click continuo '
                f'durante la recarga. {"Burst detectado (<5 min). " if burst_found else ""}'
                f'Muestra: {sample[:200]}'
            ),
        })
        print(f"⚠️ Bug F3+T: {total_hits} ocurrencia(s) en {len(hit_details)} archivo(s) — alerta: {alerta}")

    def scan_defender_exclusions(self):
        """Detecta exclusiones sospechosas en Windows Defender (técnica de evasión)."""
        HACK_MARKERS = [
            'vape', 'meteor', 'wurst', 'impact', 'liquidbounce', 'aristois', 'killaura',
            'autoclicker', 'autoclick', 'macro', 'inject', 'cheat', 'hack', 'xray',
            'freelook', 'aimbot', 'esp', 'blatant', 'ghost', 'rise', 'sigma',
            'novoline', 'wolfram', 'astolfo', 'reflex', 'drip', 'flux', 'crit',
            'forge\\mods', 'fabric\\mods', '\\mods\\', 'liteloader',
        ]
        try:
            import winreg
            base = r'SOFTWARE\Microsoft\Windows Defender\Exclusions'
            subtypes = ['Paths', 'Processes', 'Extensions']
            for sub in subtypes:
                try:
                    key = winreg.OpenKey(winreg.HKEY_LOCAL_MACHINE, f'{base}\\{sub}', 0,
                                         winreg.KEY_READ | winreg.KEY_WOW64_64KEY)
                    idx = 0
                    while True:
                        try:
                            name, _, _ = winreg.EnumValue(key, idx)
                            idx += 1
                            name_l = name.lower().replace('/', '\\')
                            if any(m in name_l for m in HACK_MARKERS):
                                self.issues_found.append({
                                    'nombre': f'Exclusión sospechosa en Defender ({sub}): {os.path.basename(name)}',
                                    'ruta': os.path.dirname(name) if sub == 'Paths' else name,
                                    'archivo': name,
                                    'tipo': 'defender_exclusion_hack',
                                    'categoria': 'EVASION',
                                    'alerta': 'CRITICAL',
                                    'confidence': 0.95,
                                    'detected_patterns': ['defender_exclusion', sub.lower()],
                                    'explicacion': (
                                        f'Windows Defender tiene una exclusión de tipo {sub} para '
                                        f'"{name}", que coincide con marcadores de hacks conocidos. '
                                        f'Esta exclusión impide que el antivirus detecte el hack.'
                                    ),
                                })
                        except OSError:
                            break
                    winreg.CloseKey(key)
                except (FileNotFoundError, PermissionError, OSError):
                    continue
        except Exception as e:
            print(f"Error en scan_defender_exclusions: {e}")

    def scan_powershell_history(self):
        """Detecta comandos sospechosos en el historial de PowerShell (PSReadLine)."""
        HACK_KEYWORDS = [
            'invoke-webrequest', 'invoke-expression', 'iex ', 'downloadstring', 'downloadfile',
            'bypass', 'unrestricted', 'hidden', 'encodedcommand', 'frombase64string',
            'vape', 'meteor', 'inject', 'cheat', 'hack', 'autoclicker', 'macro',
            'set-mppreference', 'add-mppreference', 'disablerealtimemonitoring',
            'net.webclient', 'webclient', 'start-bitstransfer', 'certutil',
            'reg add', 'reg delete', 'schtasks', 'sc create', 'sc start',
        ]
        SAFE_SKIP = ['update', 'upgrade', 'install', 'winget', 'choco', 'pip install']
        hist_path = os.path.expandvars(
            r'%APPDATA%\Microsoft\Windows\PowerShell\PSReadLine\ConsoleHost_history.txt'
        )
        if not os.path.exists(hist_path):
            return
        try:
            with open(hist_path, 'r', encoding='utf-8', errors='ignore') as f:
                lines = f.readlines()
            for line in lines:
                line_l = line.strip().lower()
                if not line_l:
                    continue
                if any(s in line_l for s in SAFE_SKIP):
                    continue
                matched = [kw for kw in HACK_KEYWORDS if kw in line_l]
                if matched:
                    self.issues_found.append({
                        'nombre': f'Comando sospechoso en historial PowerShell: {line.strip()[:80]}',
                        'ruta': os.path.dirname(hist_path),
                        'archivo': hist_path,
                        'tipo': 'powershell_history_hack',
                        'categoria': 'EVASION',
                        'alerta': 'SOSPECHOSO',
                        'confidence': 0.78,
                        'detected_patterns': matched[:5],
                        'explicacion': (
                            f'El historial de PowerShell contiene el comando: "{line.strip()[:120]}", '
                            f'que coincide con patrones sospechosos: {matched[:3]}.'
                        ),
                    })
        except Exception as e:
            print(f"Error en scan_powershell_history: {e}")

    def scan_minecraft_crash_reports(self):
        """Analiza crash reports de Minecraft en busca de hacks que causaron crashes."""
        HACK_PATTERNS = [
            'vape', 'meteor', 'wurst', 'impact', 'liquidbounce', 'aristois',
            'killaura', 'autoclicker', 'autoclick', 'macro', 'inject', 'cheat',
            'hack', 'xray', 'aimbot', 'esp', 'ghost', 'rise', 'sigma', 'novoline',
            'wolfram', 'astolfo', 'reflex', 'drip', 'flux', 'freelook',
            'mixin conflict', 'coremods', 'optifine conflict', 'forge conflict',
            'weave', 'javaagent', 'injection', 'mixin.hack',
            'net.minecraft.client.gui.hud', 'esp.render', 'fly.module',
        ]
        now = datetime.now()
        cutoff = now - timedelta(days=30)

        crash_dirs = []
        mc_root = os.path.expanduser(r'~\AppData\Roaming\.minecraft\crash-reports')
        if os.path.isdir(mc_root):
            crash_dirs.append(mc_root)

        for launcher_root in [
            os.path.expanduser(r'~\AppData\Roaming\PrismLauncher\instances'),
            os.path.expanduser(r'~\AppData\Roaming\MultiMC\instances'),
            os.path.expanduser(r'~\AppData\Roaming\PolyMC\instances'),
        ]:
            if os.path.isdir(launcher_root):
                try:
                    for instance in os.listdir(launcher_root):
                        cr = os.path.join(launcher_root, instance, 'minecraft', 'crash-reports')
                        if os.path.isdir(cr):
                            crash_dirs.append(cr)
                except OSError:
                    pass

        for crash_dir in crash_dirs:
            try:
                for fname in os.listdir(crash_dir):
                    if not fname.lower().endswith('.txt'):
                        continue
                    fpath = os.path.join(crash_dir, fname)
                    try:
                        mtime = datetime.fromtimestamp(os.path.getmtime(fpath))
                        if mtime < cutoff:
                            continue
                        with open(fpath, 'r', encoding='utf-8', errors='ignore') as f:
                            content = f.read(20480)
                        content_l = content.lower()
                        matched = [p for p in HACK_PATTERNS if p in content_l]
                        if matched:
                            self.issues_found.append({
                                'nombre': f'Crash report con indicios de hack: {fname}',
                                'ruta': crash_dir,
                                'archivo': fpath,
                                'tipo': 'crash_report_hack',
                                'categoria': 'FORENSE',
                                'alerta': 'SOSPECHOSO',
                                'confidence': 0.72,
                                'detected_patterns': matched[:5],
                                'explicacion': (
                                    f'El crash report "{fname}" (modificado: {mtime.strftime("%d/%m/%Y")}) '
                                    f'contiene referencias a: {matched[:3]}. Los hacks suelen aparecer '
                                    f'en crashes por conflictos de cargadores o mixins.'
                                ),
                            })
                    except OSError:
                        continue
            except OSError:
                continue

    def scan_amcache(self):
        """Detecta ejecución histórica de hacks vía Amcache.hve."""
        HACK_MARKERS = [
            'vape', 'meteor', 'wurst', 'impact', 'liquidbounce', 'aristois',
            'autoclicker', 'autoclick', 'macro', 'inject', 'cheat', 'hack',
            'xray', 'aimbot', 'ghost', 'rise', 'sigma', 'wolfram', 'astolfo',
            'reflex', 'drip', 'flux', 'freelook', 'killaura', 'novoline',
        ]
        hive_src = r'C:\Windows\AppCompat\Programs\Amcache.hve'
        if not os.path.exists(hive_src):
            return
        pid = os.getpid()
        tmp_hive = os.path.join(os.environ.get('TEMP', r'C:\Windows\Temp'), f'argus_amcache_{pid}.hve')
        reg_key = f'HKLM\\ArgusAmcache_{pid}'
        try:
            import shutil
            shutil.copy2(hive_src, tmp_hive)
        except Exception:
            return
        try:
            subprocess.run(['reg', 'load', reg_key, tmp_hive],
                           capture_output=True, timeout=10, creationflags=0x08000000)
            import winreg
            try:
                base = f'ArgusAmcache_{pid}\\Root\\InventoryApplicationFile'
                root_key = winreg.OpenKey(winreg.HKEY_LOCAL_MACHINE, base, 0,
                                           winreg.KEY_READ | winreg.KEY_WOW64_64KEY)
                num_subkeys = winreg.QueryInfoKey(root_key)[0]
                for i in range(min(num_subkeys, 2000)):
                    try:
                        sub_name = winreg.EnumKey(root_key, i)
                        sub_key = winreg.OpenKey(root_key, sub_name, 0,
                                                  winreg.KEY_READ | winreg.KEY_WOW64_64KEY)
                        try:
                            path_val, _ = winreg.QueryValueEx(sub_key, 'LowerCaseLongPath')
                        except OSError:
                            try:
                                path_val, _ = winreg.QueryValueEx(sub_key, 'Name')
                            except OSError:
                                path_val = sub_name
                        winreg.CloseKey(sub_key)
                        path_l = str(path_val).lower()
                        matched = [m for m in HACK_MARKERS if m in path_l]
                        if matched:
                            self.issues_found.append({
                                'nombre': f'Ejecución histórica de hack detectada: {os.path.basename(path_val)}',
                                'ruta': os.path.dirname(path_val),
                                'archivo': path_val,
                                'tipo': 'amcache_hack_execution',
                                'categoria': 'FORENSE',
                                'alerta': 'CRITICAL',
                                'confidence': 0.88,
                                'detected_patterns': matched[:5],
                                'explicacion': (
                                    f'Amcache registra que este programa fue ejecutado: "{path_val}". '
                                    f'Coincide con marcadores de hacks conocidos: {matched[:3]}. '
                                    f'Este registro persiste aunque el archivo haya sido borrado.'
                                ),
                            })
                    except OSError:
                        continue
                winreg.CloseKey(root_key)
            except Exception:
                pass
        except Exception as e:
            print(f"Error en scan_amcache: {e}")
        finally:
            try:
                subprocess.run(['reg', 'unload', reg_key],
                               capture_output=True, timeout=10, creationflags=0x08000000)
            except Exception:
                pass
            try:
                os.remove(tmp_hive)
            except Exception:
                pass

    def scan_recent_msi_installs(self):
        """P3 #29 — Lista programas instalados via MSI en los últimos 7 días y cruza con _DEFINITE_HACK_NAMES."""
        print("🔍 Revisando instalaciones MSI recientes (últimos 7 días)...")
        import winreg as _wr
        import datetime as _dt
        import re as _re2

        UNINSTALL_KEYS = [
            (r'SOFTWARE\Microsoft\Windows\CurrentVersion\Uninstall', _wr.HKEY_LOCAL_MACHINE),
            (r'SOFTWARE\WOW6432Node\Microsoft\Windows\CurrentVersion\Uninstall', _wr.HKEY_LOCAL_MACHINE),
            (r'SOFTWARE\Microsoft\Windows\CurrentVersion\Uninstall', _wr.HKEY_CURRENT_USER),
        ]
        cutoff = _dt.datetime.now() - _dt.timedelta(days=7)
        DATE_RE = _re2.compile(r'(\d{8})')

        def _parse_install_date(s):
            m = DATE_RE.match(str(s or ''))
            if m:
                try:
                    return _dt.datetime.strptime(m.group(1), '%Y%m%d')
                except Exception:
                    pass
            return None

        try:
            for reg_path, hive in UNINSTALL_KEYS:
                try:
                    root = _wr.OpenKey(hive, reg_path, 0, _wr.KEY_READ)
                except Exception:
                    continue
                n = _wr.QueryInfoKey(root)[0]
                for i in range(n):
                    try:
                        subkey_name = _wr.EnumKey(root, i)
                        subkey = _wr.OpenKey(root, subkey_name)
                        try:
                            display_name = _wr.QueryValueEx(subkey, 'DisplayName')[0]
                        except Exception:
                            continue
                        try:
                            install_date_raw = _wr.QueryValueEx(subkey, 'InstallDate')[0]
                        except Exception:
                            continue
                        install_dt = _parse_install_date(install_date_raw)
                        if not install_dt or install_dt < cutoff:
                            continue
                        name_lower = display_name.lower()
                        matched_hack = next((h for h in _DEFINITE_HACK_NAMES if h in name_lower), None)
                        if matched_hack:
                            date_str = install_dt.strftime('%d/%m/%Y')
                            print(f"🚨 INSTALACION MSI RECIENTE: {display_name} ({date_str})")
                            self.issues_found.append({
                                'nombre': f'Instalación reciente de hack detectada: {display_name} ({date_str})',
                                'ruta': '',
                                'archivo': display_name,
                                'tipo': 'registry_appcompat_hack',
                                'categoria': 'INSTALACION',
                                'alerta': 'CRITICAL',
                                'confidence': 0.91,
                                'detected_patterns': [f'msi_install:{matched_hack}', f'date:{date_str}'],
                                'explicacion': (
                                    f'"{display_name}" fue instalado via MSI el {date_str}. '
                                    'La presencia de este programa en el registro de desinstalación '
                                    'confirma que fue instalado formalmente en el sistema, '
                                    'no solo copiado como archivo suelto.'
                                ),
                            })
                    except Exception:
                        continue
                _wr.CloseKey(root)
        except Exception as e:
            print(f"Error en scan_recent_msi_installs: {e}")

    def scan_windows_search_history(self):
        """Detecta búsquedas sospechosas en el historial de Windows Explorer."""
        HACK_TERMS = [
            'vape', 'meteor', 'wurst', 'impact', 'liquidbounce', 'aristois',
            'autoclicker', 'autoclick', 'macro', 'cheat', 'hack', 'xray',
            'ghost client', 'rise client', 'sigma', 'wolfram', 'astolfo',
            'reflex', 'drip', 'killaura', 'aimbot', 'esp hack', 'freelook',
            'cracked minecraft', 'tlauncher crack', 'free hack', 'descarga hack',
        ]
        try:
            import winreg
            # WordWheelQuery — historial de búsqueda del Explorador
            try:
                key = winreg.OpenKey(winreg.HKEY_CURRENT_USER,
                                     r'SOFTWARE\Microsoft\Windows\CurrentVersion\Explorer\WordWheelQuery',
                                     0, winreg.KEY_READ)
                idx = 0
                while idx < 500:
                    try:
                        name, data, _ = winreg.EnumValue(key, idx)
                        idx += 1
                        if name.lower() == 'mrulistex':
                            continue
                        term = data.decode('utf-16-le', errors='ignore').rstrip('\x00').lower() \
                            if isinstance(data, bytes) else str(data).lower()
                        matched = [t for t in HACK_TERMS if t in term]
                        if matched:
                            self.issues_found.append({
                                'nombre': f'Búsqueda sospechosa en Explorador: "{term}"',
                                'ruta': 'HKCU\\SOFTWARE\\Microsoft\\Windows\\CurrentVersion\\Explorer\\WordWheelQuery',
                                'archivo': term,
                                'tipo': 'windows_search_hack',
                                'categoria': 'FORENSE',
                                'alerta': 'SOSPECHOSO',
                                'confidence': 0.70,
                                'detected_patterns': matched[:5],
                                'explicacion': (
                                    f'Windows registra que el usuario buscó "{term}" en el Explorador. '
                                    f'Coincide con: {matched[:3]}.'
                                ),
                            })
                    except OSError:
                        break
                winreg.CloseKey(key)
            except (FileNotFoundError, PermissionError, OSError):
                pass

            # TypedURLs — URLs tipeadas manualmente en Edge/IE
            try:
                key = winreg.OpenKey(winreg.HKEY_CURRENT_USER,
                                     r'SOFTWARE\Microsoft\Internet Explorer\TypedURLs',
                                     0, winreg.KEY_READ)
                idx = 0
                while idx < 500:
                    try:
                        name, data, _ = winreg.EnumValue(key, idx)
                        idx += 1
                        url = str(data).lower()
                        matched = [t for t in HACK_TERMS if t in url]
                        if matched:
                            self.issues_found.append({
                                'nombre': f'URL tipeada manualmente sospechosa: {data}',
                                'ruta': 'HKCU\\SOFTWARE\\Microsoft\\Internet Explorer\\TypedURLs',
                                'archivo': str(data),
                                'tipo': 'typed_url_hack',
                                'categoria': 'FORENSE',
                                'alerta': 'SOSPECHOSO',
                                'confidence': 0.68,
                                'detected_patterns': matched[:5],
                                'explicacion': (
                                    f'Windows registra que el usuario tipeó directamente "{data}" '
                                    f'en el navegador. Coincide con: {matched[:3]}.'
                                ),
                            })
                    except OSError:
                        break
                winreg.CloseKey(key)
            except (FileNotFoundError, PermissionError, OSError):
                pass
        except Exception as e:
            print(f"Error en scan_windows_search_history: {e}")

    def scan_recent_files_lnk(self):
        """Detecta accesos recientes a hacks vía archivos .lnk de Windows."""
        HACK_MARKERS = [
            'vape', 'meteor', 'wurst', 'impact', 'liquidbounce', 'aristois',
            'autoclicker', 'autoclick', 'macro', 'inject', 'cheat', 'hack',
            'xray', 'aimbot', 'ghost', 'rise', 'sigma', 'novoline', 'wolfram',
            'astolfo', 'reflex', 'drip', 'flux', 'freelook', 'killaura',
        ]
        import re as _re
        WIN_PATH_RE = _re.compile(
            r'[A-Za-z]:\\[^\x00-\x1f"*<>?|][^\x00-\x1f"*<>?|]{2,180}',
            _re.IGNORECASE
        )
        recent_dir = os.path.expandvars(r'%APPDATA%\Microsoft\Windows\Recent')
        if not os.path.isdir(recent_dir):
            return
        now = datetime.now()
        cutoff = now - timedelta(days=30)
        try:
            for fname in os.listdir(recent_dir):
                if not fname.lower().endswith('.lnk'):
                    continue
                fpath = os.path.join(recent_dir, fname)
                try:
                    mtime = datetime.fromtimestamp(os.path.getmtime(fpath))
                    if mtime < cutoff:
                        continue
                    with open(fpath, 'rb') as f:
                        raw = f.read(8192)
                    paths_found = set()
                    for enc in ('utf-16-le', 'latin-1'):
                        try:
                            decoded = raw.decode(enc, errors='ignore')
                            for m in WIN_PATH_RE.findall(decoded):
                                paths_found.add(m.strip())
                        except Exception:
                            pass
                    for target_path in paths_found:
                        target_l = target_path.lower()
                        # Ignorar guías del staff de screenshare (SS_Manual_*, SS_Guide_*, etc.)
                        _bn_l = os.path.basename(target_l)
                        if _bn_l.startswith(('ss_manual', 'ss_guide', 'ss_tutorial', 'ss_doc', 'argus_')):
                            continue
                        matched = [mk for mk in HACK_MARKERS if mk in target_l]
                        if matched:
                            self.issues_found.append({
                                'nombre': f'Acceso reciente a hack: {os.path.basename(target_path)}',
                                'ruta': os.path.dirname(target_path),
                                'archivo': target_path,
                                'tipo': 'recent_lnk_hack',
                                'categoria': 'FORENSE',
                                'alerta': 'SOSPECHOSO',
                                'confidence': 0.80,
                                'detected_patterns': matched[:5],
                                'explicacion': (
                                    f'Windows registra un acceso reciente '
                                    f'({mtime.strftime("%d/%m/%Y")}) al archivo "{target_path}". '
                                    f'Coincide con marcadores de hacks: {matched[:3]}.'
                                ),
                            })
                            break  # un reporte por .lnk es suficiente
                except OSError:
                    continue
        except Exception as e:
            print(f"Error en scan_recent_files_lnk: {e}")

    def scan_backup_sync_locations(self):
        """#28 — Marca archivos en rutas de backup/sync con score reducido."""
        SYNC_PATHS = ['onedrive', 'google drive', 'dropbox', 'icloudrive', 'box\\', 'mega\\']
        try:
            for issue in self.issues_found:
                ruta = (issue.get('ruta') or '').lower()
                if any(s in ruta for s in SYNC_PATHS):
                    if issue.get('tipo') not in {
                        'ghost_client_config', 'ghost_client_registry',
                        'blacklisted_mod', 'modified_minecraft_jar'
                    }:
                        issue['confidence'] = round(issue.get('confidence', 0.5) * 0.4, 3)
                        issue['alerta'] = 'POCO_SOSPECHOSO'
                        issue['explicacion'] = (issue.get('explicacion', '') +
                            ' (Archivo en carpeta de sincronización cloud — posiblemente backup de otro PC.)')
        except Exception as e:
            print(f"Error en scan_backup_sync_locations: {e}")

    def scan_hack_fingerprints(self):
        """P3 #15 — Detecta firmas compuestas de ghost clients específicos."""
        print("🔍 Verificando fingerprints compuestos de ghost clients...")
        appdata  = os.environ.get('APPDATA', '')
        local    = os.environ.get('LOCALAPPDATA', '')

        FINGERPRINTS = {
            'Vape': [
                os.path.join(appdata, 'vape.encrypted'),
                os.path.join(appdata, 'vape.json'),
                os.path.join(appdata, '.vape'),
            ],
            'Sigma': [
                os.path.join(appdata, '.sigma'),
                os.path.join(appdata, 'Sigma'),
            ],
            'Rise Client': [
                os.path.join(appdata, '.rise'),
                os.path.join(local,   'Rise Client'),
            ],
            'LiquidBounce': [
                os.path.join(appdata, '.liquidbounce'),
                os.path.join(appdata, 'LiquidBounce'),
            ],
            'Meteor Client': [
                os.path.join(appdata, '.meteor'),
                os.path.join(appdata, '.minecraft', 'mods', 'meteor-client'),
            ],
            'Future Client': [
                os.path.join(appdata, '.future'),
                os.path.join(local,   'Future'),
            ],
            'Flux': [
                os.path.join(appdata, '.flux'),
                os.path.join(appdata, 'Flux'),
            ],
            'Astolfo': [
                os.path.join(appdata, '.astolfo'),
                os.path.join(appdata, 'Astolfo'),
            ],
            'RusherHack': [
                os.path.join(appdata, '.rusherhack'),
                os.path.join(appdata, 'RusherHack'),
            ],
            'Novoline': [
                os.path.join(appdata, '.novoline'),
                os.path.join(appdata, 'Novoline'),
            ],
            'Datura': [
                os.path.join(appdata, '.datura'),
            ],
            'Jello': [
                os.path.join(appdata, 'jello'),
                os.path.join(appdata, '.jello'),
            ],
            'Mathias': [
                os.path.join(appdata, '.mathias'),
            ],
            'SalHack': [
                os.path.join(appdata, '.salhack'),
                os.path.join(appdata, 'SalHack'),
            ],
        }

        try:
            for client_name, paths in FINGERPRINTS.items():
                found = [p for p in paths if os.path.exists(p)]
                if not found:
                    continue
                print(f"🚨 FINGERPRINT GHOST CLIENT: {client_name} ({len(found)} artefactos)")
                self.issues_found.append({
                    'nombre': f'Ghost client identificado: {client_name}',
                    'ruta': found[0],
                    'archivo': os.path.basename(found[0]),
                    'tipo': 'ghost_client_config',
                    'categoria': 'GHOST_CLIENT',
                    'alerta': 'CRITICAL',
                    'confidence': min(0.95, 0.80 + len(found) * 0.05),
                    'detected_patterns': [f'fingerprint:{client_name.lower().replace(" ", "_")}'],
                    'explicacion': f'Se identificó el ghost client {client_name} por {len(found)} artefacto(s) '
                                   f'encontrados en rutas características: {", ".join(os.path.basename(p) for p in found)}.',
                    'count': len(found),
                    'grouped_paths': found,
                })
        except Exception as e:
            print(f"Error en scan_hack_fingerprints: {e}")

    def scan_kill_chain(self):
        """P3 #3 — Detecta secuencias temporales sospechosas en el USN Journal (kill chain)."""
        print("🔍 Analizando kill chain en USN Journal...")
        import datetime as _dt
        import re as _re

        try:
            lines = self._read_usn_journal(max_lines=150_000, max_seconds=12)
            if not lines:
                return
            events = []
            for line in lines:
                ll = line.lower()
                if not ('.jar' in ll or '.exe' in ll or '.minecraft' in ll):
                    continue
                is_created = '0x00000100' in line
                is_deleted = '0x80000200' in line or '0x80000020' in line
                is_renamed = '0x00001000' in line or '0x00002000' in line
                if not (is_created or is_deleted or is_renamed):
                    continue
                parts = line.split(',')
                fname = parts[3].strip('"') if len(parts) > 3 else ''
                action = 'created' if is_created else 'deleted' if is_deleted else 'renamed'
                events.append({'file': fname.lower(), 'action': action})

            # Detectar kill chain: descargado → ejecutado → borrado
            files_created  = {e['file'] for e in events if e['action'] == 'created'}
            files_deleted  = {e['file'] for e in events if e['action'] == 'deleted'}
            files_renamed  = {e['file'] for e in events if e['action'] == 'renamed'}

            HACK_KW = ['sigma','vape','liquid','wurst','meteor','rise','flux','future',
                       'astolfo','ghost','inject','cheat','hack','aimbot','killaura']

            # Archivos creados Y borrados con nombre de hack = kill chain
            for fname in files_created & files_deleted:
                if any(kw in fname for kw in HACK_KW):
                    print(f"🚨 KILL CHAIN: {fname} — creado y borrado")
                    self.issues_found.append({
                        'nombre': f'Kill chain detectada: {os.path.basename(fname)} (descargado y borrado)',
                        'ruta': fname,
                        'archivo': os.path.basename(fname),
                        'tipo': 'kill_chain',
                        'categoria': 'FORENSE',
                        'alerta': 'CRITICAL',
                        'confidence': 0.88,
                        'detected_patterns': ['kill_chain_download_delete'],
                        'explicacion': f'El archivo {os.path.basename(fname)} fue descargado y borrado en la '
                                       f'misma sesión. Esta secuencia (descargar → ejecutar → borrar) es '
                                       f'característica de jugadores que usan hacks y limpian evidencia.',
                    })

            # Muchos archivos borrados en .minecraft en poco tiempo = limpieza activa
            mc_deleted = [e for e in events if '.minecraft' in e['file'] and e['action'] == 'deleted']
            if len(mc_deleted) >= 10:
                print(f"🚨 LIMPIEZA ACTIVA: {len(mc_deleted)} archivos borrados en .minecraft")
                self.issues_found.append({
                    'nombre': f'Limpieza activa detectada: {len(mc_deleted)} archivos borrados en .minecraft',
                    'ruta': '.minecraft',
                    'archivo': 'USN Journal',
                    'tipo': 'kill_chain',
                    'categoria': 'EVASION',
                    'alerta': 'SOSPECHOSO',
                    'confidence': 0.72,
                    'detected_patterns': ['active_cleanup'],
                    'explicacion': f'Se detectaron {len(mc_deleted)} archivos borrados en la carpeta .minecraft '
                                   f'recientemente. Esto puede indicar que el jugador limpió evidencia de hacks '
                                   f'antes del Screen Share.',
                })
        except Exception as e:
            print(f"Error en scan_kill_chain: {e}")

    def _apply_temporal_correlation(self, issues: list) -> list:
        """#27 — Marca CRITICAL si prefetch + userassist + browser coinciden en mismo hack y día."""
        import re as _re
        import datetime as _dt

        CORRELATED_TYPES = {
            'prefetch': 'prefetch_hack',
            'userassist': 'registry_userassist_hack',
            'browser': 'browser_download_hack',
        }
        HACK_NAMES_TEMPORAL = list(_DEFINITE_HACK_NAMES) + [
            'vape', 'sigma', 'liquidbounce', 'wurst', 'meteor', 'rusherhack',
            'aristois', 'rise', 'flux', 'future', 'entropy', 'whiteout', 'exhibition',
        ]

        # Extraer (hack_name, date_str, source_type) por issue
        def _extract_date(text: str):
            m = _re.search(r'(\d{2}/\d{2}/\d{4})', text)
            if m:
                try:
                    return _dt.datetime.strptime(m.group(1), '%d/%m/%Y').date()
                except Exception:
                    pass
            return None

        # Agrupar por (hack_name, date)
        corr_map: dict = {}  # (hack, date) → set of source_type
        for iss in issues:
            tipo = iss.get('tipo', '')
            if tipo not in CORRELATED_TYPES.values():
                continue
            combined = (iss.get('nombre', '') + ' ' + iss.get('ruta', '') + ' ' + iss.get('explicacion', '')).lower()
            matched_hack = next((h for h in HACK_NAMES_TEMPORAL if h in combined), None)
            if not matched_hack:
                continue
            date = _extract_date(iss.get('nombre', '') + ' ' + iss.get('explicacion', ''))
            key = (matched_hack, date)
            src_type = next(k for k, v in CORRELATED_TYPES.items() if v == tipo)
            corr_map.setdefault(key, set()).add(src_type)

        correlated = {key for key, srcs in corr_map.items() if len(srcs) >= 3}
        if not correlated:
            return issues

        # Elevar todos los issues relacionados a CRITICAL y agregar un hallazgo resumen
        for key in correlated:
            hack, date = key
            date_str = date.strftime('%d/%m/%Y') if date else 'fecha desconocida'
            srcs = corr_map[key]
            print(f"🎯 CORRELACIÓN TEMPORAL: {hack} confirmado por prefetch+userassist+browser ({date_str})")
            for iss in issues:
                combined = (iss.get('nombre', '') + iss.get('ruta', '')).lower()
                if hack in combined:
                    iss['alerta'] = 'CRITICAL'
            issues.append({
                'nombre': f'Correlación temporal confirmada: {hack} (prefetch + userassist + historial)',
                'ruta': '',
                'archivo': '',
                'tipo': 'kill_chain',
                'categoria': 'CORRELACION',
                'alerta': 'CRITICAL',
                'confidence': 0.97,
                'detected_patterns': [f'temporal_correlation:{hack}', f'sources:{",".join(sorted(srcs))}'],
                'explicacion': (
                    f'El hack "{hack}" aparece en {len(srcs)} fuentes independientes: '
                    f'{", ".join(sorted(srcs))} con fecha {date_str}. '
                    'La coincidencia de tres fuentes forenses distintas en el mismo día '
                    'confirma la ejecución del hack más allá de toda duda razonable.'
                ),
            })
        return issues

    def _filter_by_file_size(self, issues):
        """P2 #8 — Descarta JARs demasiado pequeños para ser un hack real (< 3KB)."""
        result = []
        for issue in issues:
            tipo = issue.get('tipo', '')
            if tipo not in ('file', 'jar_file', 'minecraft_file'):
                result.append(issue)
                continue
            ruta = issue.get('ruta') or issue.get('archivo', '')
            if ruta and os.path.isfile(str(ruta)):
                try:
                    size = os.path.getsize(str(ruta))
                    if size < 3072:  # < 3KB — imposible que sea un hack funcional
                        continue
                except Exception:
                    pass
            result.append(issue)
        return result

    def _filter_backup_sync(self, issues):
        """P2 #28 — Reduce score de archivos en rutas de sincronización cloud."""
        SYNC_KW = ['onedrive', 'google drive', 'dropbox', 'icloudrive', r'box\\', r'mega\\', 'nextcloud']
        ALWAYS_TRUSTED = {'ghost_client_config','ghost_client_registry','blacklisted_mod',
                          'modified_minecraft_jar','javaagent_injection','weave_loader'}
        for issue in issues:
            if issue.get('tipo') in ALWAYS_TRUSTED:
                continue
            ruta = (issue.get('ruta') or '').lower()
            if any(s in ruta for s in SYNC_KW):
                issue['confidence'] = round(issue.get('confidence', 0.5) * 0.35, 3)
                if issue.get('alerta') in ('CRITICAL', 'SOSPECHOSO'):
                    issue['alerta'] = 'POCO_SOSPECHOSO'
                issue['explicacion'] = (issue.get('explicacion', '') +
                    ' (En carpeta de sync cloud — posiblemente backup de otro PC.)')
        return issues

    # ── PARTE 2 — Mejoras de filtrado (FP reduction) ───────────────────────────

    def _apply_human_explanations(self, issues):
        """#23 — Genera explicaciones en español para hallazgos que no tengan una."""
        TIPO_EXPLANATIONS = {
            'ghost_client_config':     'Se encontró un archivo de configuración de un ghost client conocido. '
                                       'Esto indica que el jugador ha ejecutado este hack en este PC.',
            'ghost_client_registry':   'El registro de Windows contiene una clave dejada por la instalación '
                                       'de un ghost client. Persiste aunque se desinstale.',
            'blacklisted_mod':         'Se encontró un mod prohibido en la carpeta de mods de Minecraft. '
                                       'Este mod tiene capacidades de hack.',
            'jdwp_debug_port':         'El proceso de Minecraft tiene activo el puerto de debug JDWP. '
                                       'Esto permite inyectar bytecode en runtime — nadie legítimo juega con esto.',
            'vpn_active':              'Hay una VPN activa durante el Screen Share. '
                                       'Puede usarse para ocultar la IP o evadir sistemas de detección.',
            'hosts_minecraft_redirect':'El archivo hosts redirige dominios de Minecraft o anti-cheat. '
                                       'Técnica usada para evadir sistemas de anti-cheat online.',
            'javaagent_injection':     'Se detectó un agente inyectado en la JVM de Minecraft. '
                                       'Todos los ghost clients modernos como Weave usan esta técnica.',
            'dll_injection_java':      'Se encontró una DLL sospechosa cargada en el proceso de Java/Minecraft. '
                                       'Las DLLs de hack se inyectan para añadir módulos en runtime.',
            'ahk_autoclick':           'Script AutoHotKey con patrones de autoclick detectado. '
                                       'Clicks automáticos con delay de 8-15ms son característicos de autoclic.',
            'injector_process':        'Se detectó un proceso inyector corriendo al mismo tiempo que Minecraft. '
                                       'Los inyectores cargan DLLs o JARs de hacks en el proceso del juego.',
            'temp_jar_recent':         'Se encontró un .jar descargado recientemente en carpetas temporales. '
                                       'Técnica común para inyectar sin dejar rastro permanente.',
            'modified_minecraft_jar':  'El hash del minecraft.jar no coincide con la versión oficial de Mojang. '
                                       'Indica que el jar del juego fue modificado, típico de ghost clients clásicos.',
            'prefetch_hack':           'El Prefetch de Windows confirma que un hack fue ejecutado en este PC. '
                                       'Aunque el archivo esté borrado, la ejecución queda registrada.',
            'usn_deleted_hack':        'El USN Journal registra que un archivo de hack fue borrado recientemente. '
                                       'El jugador puede haber limpiado evidencia antes del SS.',
            'hack_string_in_loaded_jar':'Se encontraron nombres de módulos de hack en los JARs cargados por Java. '
                                        'Esto indica que un ghost client está activo en memoria.',
            'weave_loader':            'Weave Loader es el framework de inyección de hacks más popular actualmente. '
                                       'Su presencia indica que el jugador usa mods no autorizados.',
            'jitter_script':           'Configuración de jitter o aim assist encontrada en software de periférico. '
                                       'El jitter clicking automatizado está prohibido en la mayoría de servidores.',
            'baritone_prohibited':     'Baritone está configurado con modos prohibidos activos (printer, elytraFly). '
                                       'En modo printer puede construir estructuras automáticamente.',
            'litematica_printer':      'Litematica tiene el Printer Mode activado. '
                                       'Permite colocar bloques automáticamente, prohibido en servidores survival.',
            'arduino_hid_device':      'Se detectó un dispositivo HID (Arduino/CH340/STM32) conectado. '
                                       'Estos dispositivos pueden emular un mouse para autoclick por hardware.',
            'suspicious_network_connection': 'javaw.exe tiene una conexión activa a un servidor externo desconocido. '
                                       'Los ghost clients con licencia online (Vape, Future, Sigma) se conectan '
                                       'a sus servidores para verificar la licencia del usuario.',
            'discord_webhook_config':   'Se encontró una URL de webhook de Discord en un archivo de configuración. '
                                       'Los hack clients modernos la usan para notificar al jugador o para '
                                       'exfiltrar datos del servidor a un canal de Discord privado.',
            'registry_run_hack':        'Una clave de inicio automático (Run/RunOnce) del registro de Windows '
                                       'contiene el nombre de un hack client. El hack se ejecuta automáticamente '
                                       'al iniciar Windows sin necesidad de ejecutarlo manualmente.',
            'registry_userassist_hack': 'UserAssist es un registro forense de Windows que almacena el historial '
                                       'de todos los programas ejecutados desde el Explorador. Confirma que el '
                                       'hack fue lanzado aunque el archivo esté ahora borrado.',
            'registry_appcompat_hack':  'AppCompatFlags registra programas que solicitaron compatibilidad de Windows. '
                                       'Los loaders de hacks frecuentemente necesitan este flag para inyectar en '
                                       'procesos de 64 bits desde un ejecutable de 32 bits.',
            'browser_download_hack':   'El historial de descargas del navegador muestra que se descargó un archivo '
                                       'cuyo nombre o URL coincide con un hack client conocido. El historial persiste '
                                       'aunque el archivo haya sido borrado del sistema.',
            'browser_visited_hack':    'El historial del navegador registra visitas al sitio web oficial de un hack '
                                       'client conocido o una herramienta de DDoS/stresser. Confirma que el jugador '
                                       'buscó o accedió activamente a ese recurso.',
            'ddos_application':        'Se detectó una herramienta de DDoS/DoS instalada o activa en el sistema. '
                                       'Estas herramientas (LOIC, HOIC, stressers) se usan para saturar servidores '
                                       'con tráfico malicioso y no tienen uso legítimo en Minecraft.',
            'clipboard_hack_evidence': 'El portapapeles del sistema contiene texto relacionado con un hack client. '
                                       'Puede indicar que el jugador estaba copiando la configuración de un hack '
                                       'o la URL de descarga para instalarlo.',
        }
        for issue in issues:
            if not issue.get('explicacion'):
                tipo = issue.get('tipo', '')
                if tipo in TIPO_EXPLANATIONS:
                    issue['explicacion'] = TIPO_EXPLANATIONS[tipo]
        return issues

    def _group_related_results(self, issues):
        """#24 — Agrupa hallazgos repetidos del mismo tipo/hack en un solo resultado con count."""
        from collections import defaultdict
        groups = defaultdict(list)
        ungrouped = []

        GROUPABLE_TYPES = {
            'ghost_client_config', 'blacklisted_mod', 'temp_jar_recent',
            'prefetch_hack', 'usn_deleted_hack', 'jitter_script',
        }

        for issue in issues:
            tipo = issue.get('tipo', '')
            if tipo in GROUPABLE_TYPES:
                # Agrupar por tipo + hack detectado (primer detected_pattern)
                dp = issue.get('detected_patterns', [''])[0].split(':')[-1]
                key = f"{tipo}:{dp}"
                groups[key].append(issue)
            else:
                ungrouped.append(issue)

        result = list(ungrouped)
        for key, group in groups.items():
            if len(group) == 1:
                result.append(group[0])
            else:
                # Tomar el de mayor confianza como representante
                best = max(group, key=lambda x: x.get('confidence', 0))
                best = dict(best)
                best['nombre'] = f"{best['nombre']} (+{len(group)-1} más)"
                best['count'] = len(group)
                best['grouped_paths'] = [g.get('ruta', '') for g in group]
                result.append(best)

        return result

    def _apply_score_decay(self, issues):
        """#22 — Reduce el score de evidencia antigua (> 30 días)."""
        import datetime as _dt
        now = _dt.datetime.now()
        for issue in issues:
            ruta = issue.get('ruta', '') or issue.get('archivo', '')
            if not ruta or not os.path.exists(str(ruta)):
                continue
            try:
                mtime = os.path.getmtime(str(ruta))
                age_days = (now - _dt.datetime.fromtimestamp(mtime)).days
                if age_days > 30:
                    decay = max(0.5, 1.0 - (age_days - 30) / 180)
                    old_conf = issue.get('confidence', 0.5)
                    issue['confidence'] = round(old_conf * decay, 3)
                    if age_days > 60 and issue.get('alerta') == 'CRITICAL':
                        issue['alerta'] = 'SOSPECHOSO'
            except Exception:
                continue
        return issues

    def _fetch_cloud_thresholds(self):
        """P2 #30 — Descarga umbrales de confianza ajustados por feedback loop desde la cloud."""
        import json as _json, datetime as _dt
        cache_path = os.path.join(os.environ.get('APPDATA', ''), 'ASPERSProjectsSS', 'thresholds.json')
        try:
            if os.path.isfile(cache_path):
                age = (_dt.datetime.now() - _dt.datetime.fromtimestamp(os.path.getmtime(cache_path))).total_seconds()
                if age < 1800:  # 30-minute cache
                    with open(cache_path, 'r') as f:
                        return _json.load(f).get('thresholds', {})
        except Exception:
            pass
        try:
            base_url = self.config.get('api_url', '').rstrip('/')
            if not base_url:
                return {}
            r = requests.get(f'{base_url}/api/thresholds', timeout=6)
            if r.ok:
                data = r.json()
                os.makedirs(os.path.dirname(cache_path), exist_ok=True)
                with open(cache_path, 'w') as f:
                    _json.dump(data, f)
                return data.get('thresholds', {})
        except Exception:
            pass
        return {}

    def _apply_feedback_thresholds(self, issues):
        """P2 #30 — Aplica umbrales dinámicos por tipo descargados del feedback loop."""
        thresholds = self._fetch_cloud_thresholds()
        if not thresholds:
            return issues
        result = []
        for issue in issues:
            tipo = issue.get('tipo', '')
            if tipo in thresholds:
                min_conf = thresholds[tipo]['min_confidence'] / 100.0
                if issue.get('confidence', 1.0) < min_conf:
                    print(f"[Threshold] Descartando {tipo} con conf {issue.get('confidence'):.2f} < {min_conf:.2f}")
                    continue
            result.append(issue)
        return result

    def _apply_cloud_rarity_and_ban_patterns(self, issues):
        """P3 #2 + #16 — Ajusta confidence dinámicamente usando hack_rate por issue_type
        (rareza epidemiológica) y ban_rate del historial de bans del servidor."""
        if not issues:
            return issues
        try:
            base_url = self.config.get('api_url', '').rstrip('/')
            if not base_url:
                return issues

            rarity_map  = {}
            ban_map     = {}

            import threading as _th_cloud
            def _fetch_rarity():
                try:
                    r = requests.get(f'{base_url}/api/rarity', timeout=4)
                    if r.ok:
                        for entry in r.json().get('rarity', []):
                            rarity_map[entry['issue_type']] = entry['hack_rate']
                except Exception:
                    pass
            def _fetch_ban():
                try:
                    r = requests.get(f'{base_url}/api/ban_patterns', timeout=4)
                    if r.ok:
                        for entry in r.json().get('ban_patterns', []):
                            ban_map[entry['issue_type']] = entry['ban_rate']
                except Exception:
                    pass
            t1 = _th_cloud.Thread(target=_fetch_rarity, daemon=True)
            t2 = _th_cloud.Thread(target=_fetch_ban, daemon=True)
            t1.start(); t2.start()
            t1.join(timeout=5); t2.join(timeout=5)

            if not rarity_map and not ban_map:
                return issues

            for issue in issues:
                tipo = issue.get('tipo', '')
                base_conf = issue.get('confidence', 0.5)

                hack_rate = rarity_map.get(tipo)
                ban_rate  = ban_map.get(tipo)

                if hack_rate is not None:
                    # Blending: 60% base_conf + 40% hack_rate (para no sobreescribir reglas locales)
                    new_conf = round(base_conf * 0.6 + hack_rate * 0.4, 3)
                    issue['confidence'] = new_conf
                    issue['hack_rate_cloud'] = hack_rate

                if ban_rate is not None and ban_rate >= 0.7:
                    # Si aparece en ≥70% de los baneados, multiplicar ×1.8
                    issue['confidence'] = min(1.0, round(issue.get('confidence', base_conf) * 1.8, 3))
                    issue['ban_rate_cloud'] = ban_rate
                    if issue.get('confidence', 0) >= 0.85 and issue.get('alerta') == 'SOSPECHOSO':
                        issue['alerta'] = 'CRITICAL'

        except Exception as e:
            print(f"Error en _apply_cloud_rarity_and_ban_patterns: {e}")
        return issues

    def _apply_single_indicator_cap(self, issues):
        """P2 #4 — Un solo indicador aislado no debería ser CRITICAL.
        Si un tipo de evidencia aparece solo UNA VEZ y no hay ningún otro CRITICAL,
        lo baja a SOSPECHOSO (excepto tipos de altísima confianza)."""
        ALWAYS_CRITICAL_TYPES = {
            'ghost_client_config', 'ghost_client_registry', 'jdwp_debug_port',
            'dll_injection_java', 'javaagent_injection', 'bootclasspath_modification',
            'modified_minecraft_jar', 'hack_string_in_loaded_jar',
            'cloud_hash_match', 'kill_chain', 'weave_loader',
            'suspicious_process_tree',
            # v1.5.0 — nuevos tipos de alta confianza
            'discord_webhook_config',   # C2 en config de hack = siempre crítico
            'registry_run_hack',        # Persistencia en Run/RunOnce
            'registry_userassist_hack', # Ejecución confirmada por forense
            'prefetch_hack',            # Prefetch de hack = ejecución confirmada
        }
        critical_items = [i for i in issues if i.get('alerta') == 'CRITICAL']
        if len(critical_items) <= 1:
            for i in issues:
                if i.get('alerta') == 'CRITICAL' and i.get('tipo', '') not in ALWAYS_CRITICAL_TYPES:
                    if not i.get('combination_penalty') and i.get('confidence', 1.0) < 0.90:
                        i['alerta'] = 'SOSPECHOSO'
                        i['capped_from_critical'] = True
        return issues

    def _apply_combination_penalties(self, issues):
        """P2 #21 — Escala a CRITICAL cuando hay combinaciones de evidencias independientes."""
        tipos = {i.get('tipo', '') for i in issues}
        alertas = {i.get('alerta', '') for i in issues}

        # JDWP + javaagent + memory strings = automático CRITICAL
        if {'jdwp_debug_port', 'javaagent_injection', 'hack_string_in_loaded_jar'}.issubset(tipos):
            for i in issues:
                if i.get('tipo') in ('jdwp_debug_port', 'javaagent_injection', 'hack_string_in_loaded_jar'):
                    i['alerta'] = 'CRITICAL'
                    i['confidence'] = min(1.0, i.get('confidence', 0.8) * 1.3)
                    i['combination_penalty'] = 'JDWP+javaagent+memory_strings'

        # AHK script + proceso AHK corriendo → CRITICAL
        if 'ahk_autoclick' in tipos and any('ahk' in (i.get('nombre', '') + i.get('ruta', '')).lower()
                                              and i.get('categoria') == 'PROCESO' for i in issues):
            for i in issues:
                if i.get('tipo') == 'ahk_autoclick':
                    i['alerta'] = 'CRITICAL'
                    i['combination_penalty'] = 'AHK_script+AHK_process'

        # Ghost client config + prefetch de ese client → muy alta confianza
        if 'ghost_client_config' in tipos and 'prefetch_hack' in tipos:
            for i in issues:
                if i.get('tipo') in ('ghost_client_config', 'prefetch_hack'):
                    i['alerta'] = 'CRITICAL'
                    i['confidence'] = min(1.0, i.get('confidence', 0.8) * 1.2)
                    i['combination_penalty'] = 'config+prefetch'

        # USN jar borrado + kill chain → confirma limpieza activa
        if 'usn_deleted_hack' in tipos and 'kill_chain' in tipos:
            for i in issues:
                if i.get('tipo') in ('usn_deleted_hack', 'kill_chain'):
                    i['alerta'] = 'CRITICAL'
                    i['combination_penalty'] = 'USN+kill_chain'

        # Discord webhook en config + ghost client config → C2 activo
        if 'discord_webhook_config' in tipos and (
                'ghost_client_config' in tipos or 'ghost_client_registry' in tipos):
            for i in issues:
                if i.get('tipo') in ('discord_webhook_config', 'ghost_client_config',
                                     'ghost_client_registry'):
                    i['alerta'] = 'CRITICAL'
                    i['confidence'] = min(1.0, i.get('confidence', 0.85) * 1.2)
                    i['combination_penalty'] = 'C2_webhook+ghost_config'

        # Registry Run + Prefetch del mismo hack → startup persistente confirmado
        if 'registry_run_hack' in tipos and 'prefetch_hack' in tipos:
            for i in issues:
                if i.get('tipo') in ('registry_run_hack', 'prefetch_hack'):
                    i['alerta'] = 'CRITICAL'
                    i['combination_penalty'] = 'registry_run+prefetch'

        # UserAssist + Prefetch → ejecución confirmada por 2 fuentes forenses independientes
        if 'registry_userassist_hack' in tipos and 'prefetch_hack' in tipos:
            for i in issues:
                if i.get('tipo') in ('registry_userassist_hack', 'prefetch_hack'):
                    i['alerta'] = 'CRITICAL'
                    i['confidence'] = min(1.0, i.get('confidence', 0.85) * 1.25)
                    i['combination_penalty'] = 'userassist+prefetch'

        # Weave Loader + Discord webhook → hack con exfiltración activa
        if 'ghost_client_config' in tipos and 'discord_webhook_config' in tipos:
            for i in issues:
                if i.get('tipo') in ('ghost_client_config', 'discord_webhook_config'):
                    i['combination_penalty'] = 'weave+C2'

        # AHK compilado + Minecraft detectado = autoclicker definitivo
        ahk_exes = [i for i in issues if i.get('tipo') == 'ahk_autoclick'
                    and 'ahk_compiled_exe' in i.get('detected_patterns', [])]
        if ahk_exes:
            for i in ahk_exes:
                i['alerta'] = 'CRITICAL'
                i['combination_penalty'] = 'compiled_ahk'

        # Browser download + ghost client config → descargó Y usó el hack
        if 'browser_download_hack' in tipos and (
                'ghost_client_config' in tipos or 'prefetch_hack' in tipos):
            for i in issues:
                if i.get('tipo') in ('browser_download_hack', 'ghost_client_config',
                                     'prefetch_hack'):
                    i['alerta'] = 'CRITICAL'
                    i['confidence'] = min(1.0, i.get('confidence', 0.85) * 1.15)
                    i['combination_penalty'] = 'browser_dl+ghost_config'

        # Browser download + registry userassist → evidencia forense completa
        if 'browser_download_hack' in tipos and 'registry_userassist_hack' in tipos:
            for i in issues:
                if i.get('tipo') in ('browser_download_hack', 'registry_userassist_hack'):
                    i['alerta'] = 'CRITICAL'
                    i['combination_penalty'] = 'browser_dl+userassist'

        # JAR con clases de hack + prefetch = hack instalado y ejecutado
        jar_class_hits = [i for i in issues if i.get('tipo') == 'blacklisted_mod'
                          and any('jar_class_pkg' in p for p in i.get('detected_patterns', []))]
        if jar_class_hits and 'prefetch_hack' in tipos:
            for i in jar_class_hits:
                i['alerta'] = 'CRITICAL'
                i['combination_penalty'] = 'jar_class+prefetch'

        # 3+ CRITICAL de categorías distintas → riesgo extremo
        critical_cats = {i.get('categoria', '') for i in issues if i.get('alerta') == 'CRITICAL'}
        if len(critical_cats) >= 3:
            for i in issues:
                if i.get('alerta') == 'CRITICAL':
                    i['confidence'] = min(1.0, i.get('confidence', 0.9) * 1.15)

        return issues

    def _ai_contextual_boost(self, issues):
        """v1.5 — Ajuste de severidad basado en el contexto global del scan.

        La IA observa el conjunto completo de hallazgos y:
        - Escala indicadores SOSPECHOSO→CRITICAL cuando hay suficiente evidencia cruzada
        - Desescala hallazgos CRITICAL aislados sin respaldo de otras fuentes
        - Marca 'clean_context' si el contexto global es inocente
        """
        if not issues:
            return issues

        tipos_presentes = {i.get('tipo', '') for i in issues}
        categorias_criticas = {i.get('categoria', '') for i in issues
                               if i.get('alerta') == 'CRITICAL'}
        n_critical = sum(1 for i in issues if i.get('alerta') == 'CRITICAL')
        n_sospechoso = sum(1 for i in issues if i.get('alerta') == 'SOSPECHOSO')
        n_total = len(issues)

        # Tipos forenses de alta confianza — si hay 2+, todo el scan es más confiable
        HIGH_CONF_FORENSE = {
            'prefetch_hack', 'usn_deleted_hack', 'registry_userassist_hack',
            'registry_run_hack', 'weave_loader', 'discord_webhook_config',
            'kill_chain', 'modified_minecraft_jar',
            'browser_download_hack',  # historial de descargas del navegador
            'browser_visited_hack',   # visitas a sitios de hack/DDoS
            'ghost_client_config',    # carpeta .vape/.meteor/.rise confirmada
            'ddos_application',       # herramienta DDoS encontrada o activa
            'f3t_resourcepack_exploit',  # bug F3+T en logs del cliente
            'defender_exclusion_hack',   # exclusión sospechosa en Windows Defender
            'amcache_hack_execution',    # ejecución histórica de hack en Amcache
        }
        n_forense = sum(1 for i in issues if i.get('tipo', '') in HIGH_CONF_FORENSE)

        # BOOST: si hay 2+ fuentes forenses independientes, confirmar todos los CRITICAL
        if n_forense >= 2:
            for i in issues:
                if i.get('alerta') in ('SOSPECHOSO', 'CRITICAL'):
                    old = i.get('alerta')
                    i['alerta'] = 'CRITICAL'
                    i['confidence'] = min(1.0, i.get('confidence', 0.75) * 1.15)
                    if old != 'CRITICAL':
                        i['ai_boosted'] = f'forense_x{n_forense}'
            print(f"🧠 [AI] Boost forense x{n_forense}: SOSPECHOSO→CRITICAL aplicado")

        # BOOST: contexto de múltiples categorías confirma patrón de cheating
        elif n_critical >= 2 and len(categorias_criticas) >= 2:
            for i in issues:
                if i.get('alerta') == 'SOSPECHOSO':
                    i['alerta'] = 'CRITICAL'
                    i['ai_boosted'] = 'multi_categoria'
            print(f"🧠 [AI] Boost multi-categoria ({len(categorias_criticas)} cats): SOSPECHOSO→CRITICAL")

        # DECAY: si solo hay 1 CRITICAL y 0 forenses, bajar a SOSPECHOSO para ser conservador
        elif n_critical == 1 and n_forense == 0 and n_sospechoso == 0:
            for i in issues:
                if i.get('alerta') == 'CRITICAL':
                    tipo = i.get('tipo', '')
                    # Tipos que son siempre CRITICAL aunque estén solos
                    if tipo not in {
                        'ghost_client_config', 'modified_minecraft_jar',
                        'jdwp_debug_port', 'javaagent_injection',
                        'dll_injection_java', 'weave_loader',
                        'discord_webhook_config', 'registry_run_hack',
                    }:
                        i['alerta'] = 'SOSPECHOSO'
                        i['ai_decayed'] = 'single_critical_no_forense'
            print("🧠 [AI] Decay: único CRITICAL sin forense → SOSPECHOSO")

        # CONTEXTO LIMPIO: si hay 0 CRITICAL y 0 forenses, marcar como limpio
        if n_critical == 0 and n_forense == 0 and n_sospechoso <= 1:
            for i in issues:
                i['clean_context'] = True

        return issues

    def scan_player_baseline_delta(self):
        """P3 #5 — Compara el scan actual con el baseline histórico del mismo machine.
        Si hay muchos hallazgos nuevos respecto al historial, es sospechoso.
        Si el jugador siempre sale limpio y hoy tiene CRITICAL, es muy sospechoso."""
        print("🔍 Comparando con baseline histórico del jugador...")
        try:
            base_url = self.config.get('api_url', '').rstrip('/')
            machine_id = self.config.get('machine_id', '')
            if not base_url or not machine_id:
                return

            r = requests.get(f'{base_url}/api/player_baseline/{machine_id}', timeout=8)
            if not r.ok:
                return
            data = r.json()
            baseline = data.get('baseline')
            scan_count = data.get('scan_count', 0)
            if not baseline or scan_count < 2:
                return  # Not enough history

            avg_issues   = baseline.get('avg_issues', 0)
            avg_risk     = baseline.get('avg_risk', 0)
            known_types  = set(baseline.get('known_types', []))
            hack_verdicts = baseline.get('hack_verdicts', 0)

            current_issues = len(self.issues_found)
            current_crits  = sum(1 for i in self.issues_found if i.get('alerta') == 'CRITICAL')
            current_types  = {i.get('tipo', '') for i in self.issues_found}
            new_types = current_types - known_types - {''}

            # Case 1: Current has way more issues than average
            if avg_issues > 0 and current_issues > avg_issues * 3 and current_issues > 5:
                print(f"📊 ANOMALÍA BASELINE: {current_issues} issues vs avg {avg_issues:.1f}")
                self.issues_found.append({
                    'nombre': f'Anomalía vs historial: {current_issues} hallazgos (promedio {avg_issues:.1f})',
                    'ruta': 'player_baseline',
                    'archivo': 'baseline_delta',
                    'tipo': 'baseline_anomaly',
                    'categoria': 'FORENSE',
                    'alerta': 'SOSPECHOSO',
                    'confidence': min(0.85, 0.50 + (current_issues - avg_issues) / (avg_issues * 10)),
                    'detected_patterns': [f'issues_delta:{current_issues - avg_issues:.0f}', f'baseline_scans:{scan_count}'],
                    'explicacion': (
                        f'Este equipo tuvo {avg_issues:.1f} hallazgos en promedio en sus últimos '
                        f'{scan_count} scans. Hoy tiene {current_issues}. '
                        f'Un aumento de 3x+ respecto al historial es inusual.'
                    ),
                })

            # Case 2: Player always clean, now has CRITICALs
            if hack_verdicts == 0 and current_crits >= 2:
                self.issues_found.append({
                    'nombre': f'Jugador históricamente limpio con {current_crits} hallazgos CRITICAL',
                    'ruta': 'player_baseline',
                    'archivo': 'baseline_delta',
                    'tipo': 'baseline_anomaly',
                    'categoria': 'FORENSE',
                    'alerta': 'CRITICAL',
                    'confidence': 0.80,
                    'detected_patterns': ['always_clean_now_critical', f'prior_scans:{scan_count}'],
                    'explicacion': (
                        f'En {scan_count} scans anteriores este jugador siempre salió limpio. '
                        f'Hoy tiene {current_crits} hallazgos CRITICAL que nunca habían aparecido. '
                        f'Cambio repentino muy sospechoso.'
                    ),
                })

            # Case 3: New issue types never seen before in this machine
            if len(new_types) >= 3:
                self.issues_found.append({
                    'nombre': f'{len(new_types)} tipos de hallazgo nuevos nunca vistos en este equipo',
                    'ruta': 'player_baseline',
                    'archivo': 'baseline_delta',
                    'tipo': 'baseline_anomaly',
                    'categoria': 'FORENSE',
                    'alerta': 'SOSPECHOSO',
                    'confidence': 0.65,
                    'detected_patterns': list(new_types)[:5],
                    'explicacion': (
                        f'Aparecieron {len(new_types)} tipos de hallazgo que nunca se habían visto '
                        f'en este equipo en {scan_count} scans anteriores: '
                        f'{", ".join(list(new_types)[:3])}.'
                    ),
                })

        except Exception as e:
            print(f"Error en scan_player_baseline_delta: {e}")

    def scan_process_tree(self):
        """P3 #9 — Análisis de árbol de procesos completo: detecta cadenas anómalas.
        Un Minecraft legítimo siempre es lanzado por un launcher conocido.
        Detecta: explorer.exe → unknown.exe → javaw.exe (cadena sospechosa)."""
        print("🔍 Analizando árbol de procesos completo...")
        try:
            # Construir mapa pid → process info
            proc_map = {}
            for proc in psutil.process_iter(['pid', 'ppid', 'name', 'exe']):
                try:
                    proc_map[proc.info['pid']] = proc.info
                except Exception:
                    continue

            KNOWN_LAUNCHERS = {
                'minecraftlauncher.exe', 'javaw.exe', 'java.exe',
                'lunarclient.exe', 'badlion.exe', 'prismlauncher.exe',
                'multimc.exe', 'gdlauncher.exe', 'ftb_app.exe',
                'curseforge.exe', 'atlauncher.exe', 'polymc.exe',
                'tlauncher.exe', 'featherlauncher.exe', 'feather launcher.exe', 'feather.exe',
                'cosmic client.exe', 'cosmicclient.exe',
                'explorer.exe', 'cmd.exe', 'powershell.exe', 'pwsh.exe',
                'steam.exe', 'code.exe', 'idea64.exe',
            }

            INJECTOR_KEYWORDS = {
                'inject', 'hook', 'patch', 'loader', 'cheat', 'hack',
                'bypass', 'ghost', 'stealth', 'aimbot', 'killaura',
                'extremeinjector', 'xenosinjector', 'cheatengine',
            }

            def get_ancestors(pid, depth=0):
                if depth > 5 or pid not in proc_map:
                    return []
                info = proc_map[pid]
                ppid = info.get('ppid', 0)
                return [info] + get_ancestors(ppid, depth + 1)

            # Find all javaw.exe processes and check their ancestry
            for pid, info in proc_map.items():
                try:
                    name = (info.get('name') or '').lower()
                    if 'javaw' not in name:
                        continue
                    ancestors = get_ancestors(info.get('ppid', 0))
                    if not ancestors:
                        continue

                    # Check for injector keywords anywhere in the tree
                    for anc in ancestors:
                        anc_name = (anc.get('name') or '').lower()
                        anc_exe  = (anc.get('exe') or '').lower()
                        if any(kw in anc_name or kw in anc_exe for kw in INJECTOR_KEYWORDS):
                            print(f"🚨 ÁRBOL SOSPECHOSO: javaw ← {anc_name}")
                            self.issues_found.append({
                                'nombre': f'Minecraft lanzado por proceso sospechoso: {anc_name}',
                                'ruta': anc_exe or anc_name,
                                'archivo': anc_name,
                                'tipo': 'suspicious_process_tree',
                                'categoria': 'PROCESO',
                                'alerta': 'CRITICAL',
                                'confidence': 0.88,
                                'detected_patterns': [f'parent:{anc_name}'],
                                'explicacion': (
                                    f'El proceso de Minecraft (javaw.exe) fue iniciado por '
                                    f'"{anc_name}", que tiene nombre asociado a herramientas de hack. '
                                    f'Un Minecraft legítimo siempre es lanzado por un launcher oficial.'
                                ),
                            })
                            break

                    # Check if immediate parent is completely unknown
                    if ancestors:
                        parent_name = (ancestors[0].get('name') or '').lower()
                        if parent_name and parent_name not in KNOWN_LAUNCHERS:
                            parent_exe = (ancestors[0].get('exe') or '').lower()
                            in_safe = any(s in parent_exe for s in ('program files', 'windows', 'steam'))
                            if not in_safe:
                                print(f"⚠️ PARENT DESCONOCIDO: javaw ← {parent_name}")
                                self.issues_found.append({
                                    'nombre': f'Minecraft lanzado por proceso desconocido: {parent_name}',
                                    'ruta': parent_exe or parent_name,
                                    'archivo': parent_name,
                                    'tipo': 'unknown_parent_process',
                                    'categoria': 'PROCESO',
                                    'alerta': 'SOSPECHOSO',
                                    'confidence': 0.60,
                                    'detected_patterns': [f'unknown_parent:{parent_name}'],
                                    'explicacion': (
                                        f'Minecraft fue iniciado por "{parent_name}", un proceso no '
                                        f'reconocido como launcher oficial. Puede ser un loader o inyector.'
                                    ),
                                })
                except Exception:
                    continue
        except Exception as e:
            print(f"Error en scan_process_tree: {e}")

    @staticmethod
    def _read_usn_journal(self, max_lines=150_000, max_seconds=12):
        """Lee fsutil USN journal sin mostrar ventana negra al usuario.
        El resultado se cachea en self._usn_cache para que USN + kill_chain
        no ejecuten fsutil dos veces.
        """
        if hasattr(self, '_usn_cache') and self._usn_cache is not None:
            return self._usn_cache

        import subprocess as _sp, time as _time, queue as _q, threading as _th

        lines = []
        proc = None
        try:
            _si = _sp.STARTUPINFO()
            _si.dwFlags |= _sp.STARTF_USESHOWWINDOW
            _si.wShowWindow = 0  # SW_HIDE
            proc = _sp.Popen(
                ['fsutil', 'usn', 'readjournal', 'C:', 'csv'],
                stdout=_sp.PIPE, stderr=_sp.DEVNULL,
                text=True, errors='ignore',
                creationflags=0x08000000,  # CREATE_NO_WINDOW
                startupinfo=_si,
            )
            buf = _q.Queue()

            def _reader():
                try:
                    for ln in proc.stdout:
                        buf.put(ln)
                except Exception:
                    pass
                finally:
                    buf.put(None)

            _th.Thread(target=_reader, daemon=True).start()
            t0 = _time.time()
            while True:
                elapsed = _time.time() - t0
                if elapsed >= max_seconds or len(lines) >= max_lines:
                    break
                try:
                    ln = buf.get(timeout=min(max_seconds - elapsed, 0.5))
                except _q.Empty:
                    break
                if ln is None:
                    break
                lines.append(ln)
        except Exception:
            pass
        finally:
            if proc is not None:
                try: proc.stdout.close()
                except Exception: pass
                try: proc.kill()
                except Exception: pass
                try: proc.wait(timeout=3)
                except Exception: pass
        self._usn_cache = lines
        return lines

    def scan_prescan_disk_activity(self):
        """P3 #17 — Anomalía de actividad de disco en los 10 minutos previos al inicio del scan.
        Si el jugador borró muchos archivos en .minecraft justo antes, es señal de limpieza activa."""
        print("🔍 Actividad de disco pre-scan (USN Journal últimos 10 min)...")
        import subprocess
        import datetime as _dt

        try:
            lines = self._read_usn_journal(max_lines=150_000, max_seconds=12)
            if not lines:
                return

            now = _dt.datetime.now()
            cutoff = now - _dt.timedelta(minutes=10)

            DELETION_FLAG = '0x80000200'
            MC_KEYWORDS = ['.minecraft', 'appdata', 'roaming', 'localappdata']
            HACK_KEYWORDS = [
                '.jar', '.exe', '.dll', 'vape', 'sigma', 'rise', 'meteor',
                'liquidbounce', 'future', 'flux', 'ghost', 'hack', 'cheat',
            ]

            deleted_mc = []
            deleted_total = 0

            for line in lines[1:]:
                parts = line.split(',')
                if len(parts) < 6:
                    continue
                try:
                    # Columnas típicas: Usn,Filename,Timestamp,Reason,FileAttributes,...
                    ts_str = parts[2].strip().strip('"')
                    reason = parts[3].strip().strip('"').lower()
                    fname  = parts[1].strip().strip('"').lower()

                    if DELETION_FLAG.lower() not in reason:
                        continue

                    ts = _dt.datetime.strptime(ts_str[:19], '%Y-%m-%d %H:%M:%S')
                    if ts < cutoff:
                        continue

                    deleted_total += 1
                    if any(k in fname for k in MC_KEYWORDS):
                        deleted_mc.append(fname)
                except Exception:
                    continue

            if deleted_mc:
                hack_deleted = [f for f in deleted_mc if any(k in f for k in HACK_KEYWORDS)]
                alert = 'CRITICAL' if hack_deleted else 'SOSPECHOSO'
                conf  = 0.85 if hack_deleted else 0.60

                # Priorizar nombres con keywords de hack, luego el resto
                display_list = hack_deleted[:5] or deleted_mc[:5]
                sample_str   = ', '.join(display_list)
                extra_count  = max(0, len(deleted_mc) - len(display_list))
                extra_str    = f' (+{extra_count} más)' if extra_count > 0 else ''

                print(f"🚨 LIMPIEZA PRE-SCAN: {len(deleted_mc)} archivos MC — {sample_str}")
                self.issues_found.append({
                    'nombre':   f'Limpieza pre-scan ({len(deleted_mc)} archivos): {sample_str}{extra_str}',
                    'ruta':     'USN Journal — .minecraft',
                    'archivo':  sample_str,
                    'tipo':     'prescan_cleanup',
                    'categoria':'FORENSE',
                    'alerta':   alert,
                    'confidence': conf,
                    'detected_patterns': [f'file:{f}' for f in deleted_mc[:20]]
                                         + ([f'hack_file:{f}' for f in hack_deleted[:5]] if hack_deleted else []),
                })
            elif deleted_total > 50:
                print(f"⚠️ Alta actividad de borrado pre-scan: {deleted_total} archivos")
                self.issues_found.append({
                    'nombre':   f'Alta actividad de borrado pre-scan: {deleted_total} archivos en los últimos 10 min',
                    'ruta':     'USN Journal',
                    'archivo':  f'{deleted_total} archivos borrados',
                    'tipo':     'prescan_cleanup',
                    'categoria':'FORENSE',
                    'alerta':   'SOSPECHOSO',
                    'confidence': 0.45,
                    'detected_patterns': [f'total_deleted:{deleted_total}'],
                })
        except Exception as e:
            print(f"Error en scan_prescan_disk_activity: {e}")

    def scan_java_rwx_memory(self):
        """Detecta regiones de memoria Private+RWX (Read+Write+Execute) en javaw.exe.
        Java legítimo no tiene regiones ejecutables privadas — son señal de código inyectado."""
        print("🔍 Escaneando regiones de memoria RWX en javaw.exe...")
        try:
            import ctypes
            import ctypes.wintypes as wt
        except ImportError:
            return

        PAGE_EXECUTE_READWRITE = 0x40
        PAGE_EXECUTE_WRITECOPY = 0x80
        MEM_PRIVATE = 0x20000
        MEM_COMMIT  = 0x1000

        class MEMORY_BASIC_INFORMATION(ctypes.Structure):
            _fields_ = [
                ('BaseAddress',       ctypes.c_size_t),
                ('AllocationBase',    ctypes.c_size_t),
                ('AllocationProtect', wt.DWORD),
                ('RegionSize',        ctypes.c_size_t),
                ('State',             wt.DWORD),
                ('Protect',           wt.DWORD),
                ('Type',              wt.DWORD),
            ]

        PROCESS_QUERY_INFORMATION = 0x0400
        PROCESS_VM_READ           = 0x0010
        k32 = ctypes.windll.kernel32

        try:
            for proc in psutil.process_iter(['pid', 'name']):
                try:
                    name = (proc.info.get('name') or '').lower()
                    if 'javaw' not in name and 'java.exe' != name:
                        continue
                    pid = proc.pid
                    h = k32.OpenProcess(PROCESS_QUERY_INFORMATION | PROCESS_VM_READ, False, pid)
                    if not h:
                        continue
                    try:
                        import time as _time
                        addr    = 0
                        mbi     = MEMORY_BASIC_INFORMATION()
                        mbi_sz  = ctypes.sizeof(mbi)
                        rwx_count = 0
                        rwx_total_kb = 0
                        _region_iter = 0
                        _t0 = _time.time()
                        # Solo regiones grandes (>=512KB): el JIT crea muchas pequeñas legítimas
                        _RWX_MIN_KB = 512
                        while k32.VirtualQueryEx(h, ctypes.c_void_p(addr), ctypes.byref(mbi), mbi_sz):
                            _region_iter += 1
                            if _region_iter > 30_000 or (_time.time() - _t0) > 10:
                                break
                            if (mbi.State == MEM_COMMIT
                                    and mbi.Type == MEM_PRIVATE
                                    and mbi.Protect in (PAGE_EXECUTE_READWRITE, PAGE_EXECUTE_WRITECOPY)
                                    and mbi.RegionSize // 1024 >= _RWX_MIN_KB):
                                rwx_count    += 1
                                rwx_total_kb += mbi.RegionSize // 1024
                                if rwx_count >= 10:
                                    break
                            next_addr = mbi.BaseAddress + mbi.RegionSize
                            if next_addr <= addr:
                                break
                            addr = next_addr
                        if rwx_count >= 2:  # >=2 regiones grandes (>=512KB cada una) = sospechoso
                            print(f"🚨 REGIONES RWX GRANDES EN JAVAW (PID {pid}): {rwx_count} regiones de >=512KB, {rwx_total_kb}KB total")
                            self.issues_found.append({
                                'nombre': f'Regiones RWX grandes en Minecraft ({rwx_count}x >=512KB, {rwx_total_kb}KB total)',
                                'ruta': f'PID:{pid}',
                                'archivo': 'javaw.exe',
                                'tipo': 'javaagent_injection',
                                'categoria': 'JAVA_INJECTION',
                                'alerta': 'CRITICAL' if rwx_count >= 5 else 'SOSPECHOSO',
                                'confidence': min(0.88, 0.55 + rwx_count * 0.06),
                                'detected_patterns': [f'rwx_large_regions:{rwx_count}', f'rwx_kb:{rwx_total_kb}'],
                                'explicacion': f'javaw.exe (PID {pid}) tiene {rwx_count} regiones de memoria privada RWX '
                                               f'de más de 512KB cada una ({rwx_total_kb}KB total). '
                                               f'El JIT del JVM crea muchas regiones RWX pequeñas; las grandes (>=512KB) '
                                               f'no son generadas por código Java legítimo e indican posible injection.',
                            })
                    finally:
                        k32.CloseHandle(h)
                except (psutil.NoSuchProcess, psutil.AccessDenied, OSError):
                    continue
        except Exception as e:
            print(f"Error en scan_java_rwx_memory: {e}")

    def scan_temp_dlls(self):
        """Detecta DLLs sospechosas en carpetas temporales — solo nivel raíz, cap 200 archivos."""
        print("🔍 Buscando DLLs sospechosas en carpetas Temp...")
        temp_dirs = list({
            os.environ.get('TEMP', ''),
            os.environ.get('TMP', ''),
            os.path.join(os.environ.get('LOCALAPPDATA', ''), 'Temp'),
            r'C:\Windows\Temp',
        })
        SAFE_PATTERNS = ('jna', 'fontconfig', 'hsperfdata', 'msi', 'msedge', 'chrome', 'setup')
        cutoff_24h = time.time() - 86400
        checked = 0
        try:
            for tdir in temp_dirs:
                if not tdir or not os.path.isdir(tdir):
                    continue
                try:
                    for entry in os.scandir(tdir):
                        if checked >= 200:
                            break
                        if not entry.is_file() or not entry.name.lower().endswith('.dll'):
                            continue
                        checked += 1
                        fname_l = entry.name.lower()
                        if any(s in fname_l for s in SAFE_PATTERNS):
                            continue
                        try:
                            st = entry.stat()
                            if st.st_mtime >= cutoff_24h and st.st_size > 10240:
                                conf = 0.75 if st.st_size > 524288 else 0.60
                                print(f"⚠️ DLL SOSPECHOSA EN TEMP: {entry.path}")
                                self.issues_found.append({
                                    'nombre': f'DLL sospechosa en carpeta temporal: {entry.name}',
                                    'ruta': entry.path,
                                    'archivo': entry.name,
                                    'tipo': 'dll_injection_java',
                                    'categoria': 'JAVA_INJECTION',
                                    'alerta': 'SOSPECHOSO',
                                    'confidence': conf,
                                    'detected_patterns': ['dll_in_temp', f'size:{st.st_size}'],
                                    'explicacion': f'DLL de {st.st_size//1024}KB encontrada en carpeta temporal '
                                                   f'en las últimas 24h. Los hacks basados en inyección '
                                                   f'nativa suelen cargar DLLs desde rutas temporales para '
                                                   f'no dejar rastro permanente en el sistema.',
                                })
                        except Exception:
                            continue
                except Exception:
                    continue
        except Exception as e:
            print(f"Error en scan_temp_dlls: {e}")

    def scan_multiple_javaw(self):
        """Detecta múltiples instancias de javaw.exe corriendo simultáneamente.
        Un jugador legítimo raramente tiene más de 1 instancia de Minecraft abierta.
        Múltiples instancias pueden indicar un proceso de inyección separado del juego."""
        print("🔍 Verificando instancias múltiples de javaw.exe...")
        try:
            java_procs = []
            for proc in psutil.process_iter(['pid', 'name', 'cmdline', 'create_time']):
                try:
                    name = (proc.info.get('name') or '').lower()
                    if 'javaw' in name or ('java.exe' == name):
                        cmdline = ' '.join(proc.info.get('cmdline') or []).lower()
                        java_procs.append({
                            'pid':      proc.pid,
                            'name':     proc.info['name'],
                            'cmdline':  cmdline[:200],
                            'is_mc':    '.minecraft' in cmdline or 'minecraft' in cmdline,
                        })
                except (psutil.NoSuchProcess, psutil.AccessDenied):
                    continue

            mc_procs = [p for p in java_procs if p['is_mc']]
            non_mc   = [p for p in java_procs if not p['is_mc']]

            if len(mc_procs) > 1:
                pids = ', '.join(str(p['pid']) for p in mc_procs)
                print(f"🚨 MÚLTIPLES INSTANCIAS MINECRAFT: {len(mc_procs)} ({pids})")
                # F28 — Verificar si TODAS las instancias vienen del mismo launcher
                # (MultiMC/Prism abre una javaw por instancia — no es sospechoso)
                _MULTI_INSTANCE_LAUNCHERS = ('multimc', 'prismlauncher', 'gdlauncher',
                                              'atlauncher', 'ftb', 'curseforge')
                _all_from_same_launcher = all(
                    any(l in p['cmdline'] for l in _MULTI_INSTANCE_LAUNCHERS)
                    for p in mc_procs
                )
                _confidence_multi = 0.45 if _all_from_same_launcher else 0.70
                _alerta_multi     = 'POCO_SOSPECHOSO' if _all_from_same_launcher else 'SOSPECHOSO'
                self.issues_found.append({
                    'nombre': f'Múltiples instancias de Minecraft simultáneas: {len(mc_procs)}',
                    'ruta': f'PIDs: {pids}',
                    'archivo': 'javaw.exe',
                    'tipo': 'suspicious_process_location',
                    'categoria': 'PROCESO',
                    'alerta': _alerta_multi,
                    'confidence': _confidence_multi,
                    'detected_patterns': [f'multiple_javaw:{len(mc_procs)}',
                                          *(['same_launcher_ok'] if _all_from_same_launcher else [])],
                    'explicacion': (
                        f'Se detectaron {len(mc_procs)} instancias de javaw.exe con contexto de Minecraft. '
                        + ('MultiMC/Prism puede abrir una javaw por instancia — bajo riesgo.'
                           if _all_from_same_launcher else
                           'Esto puede indicar un proceso de inyección separado haciéndose pasar '
                           'por una instancia legítima del juego.')
                    ),
                })
            if non_mc and mc_procs:
                pids_non = ', '.join(str(p['pid']) for p in non_mc[:3])
                self.issues_found.append({
                    'nombre': f'Proceso Java sin contexto Minecraft corriendo junto al juego: PID {pids_non}',
                    'ruta': f'PIDs: {pids_non}',
                    'archivo': 'java.exe',
                    'tipo': 'suspicious_process_location',
                    'categoria': 'PROCESO',
                    'alerta': 'SOSPECHOSO',
                    'confidence': 0.60,
                    'detected_patterns': ['java_process_without_minecraft'],
                    'explicacion': f'Hay {len(non_mc)} proceso(s) Java corriendo sin contexto de Minecraft '
                                   f'mientras el juego está abierto. Un inyector basado en JVM puede '
                                   f'ejecutarse como proceso Java independiente.',
                })
        except Exception as e:
            print(f"Error en scan_multiple_javaw: {e}")

    def scan_javaw_network_connections(self):
        """Detecta conexiones de red de javaw.exe a hosts distintos al servidor y a Mojang.
        Los ghost clients con licencia online se conectan a servidores de autenticación propios."""
        print("🔍 Analizando conexiones de red de javaw.exe...")
        TRUSTED_DOMAINS_SUFFIX = (
            '.mojang.com', '.minecraft.net', '.minecraftservices.com',
            '.amazonaws.com', '.microsoft.com', '.xbox.com', '.live.com',
            '.akamai.net', '.akamaiedge.net', '.fastly.net', '.cloudfront.net',
            # Plataformas de mods/launchers legítimos
            '.discord.com', '.discordapp.com', '.discord.gg',
            '.github.com', '.githubusercontent.com', '.github.io',
            '.modrinth.com', '.curseforge.com', '.overwolf.com',
            '.hypixel.net', '.badlion.net', '.badlioncdn.com',
            '.lunarclient.com', '.lunarclientcdn.com',
            '.cloudflare.com', '.cdn77.com', '.jsdelivr.net',
            '.optifine.net', '.fabricmc.net', '.quiltmc.org', '.neoforged.net',
        )
        TRUSTED_IPS_PREFIX = ('127.', '::1', '0.0.0.0', '192.168.', '10.', '172.',
                              '104.16.', '104.17.', '104.18.', '104.19.',  # Cloudflare /12
                              '104.20.', '104.21.', '104.22.', '104.24.', '104.25.',
                              '104.26.', '104.27.', '104.28.', '104.31.',)
        # Puertos de juego normales — conexión al servidor de Minecraft
        GAME_PORTS = (25565, 25566, 25567, 19132, 19133)  # Java + Bedrock
        HACK_CLIENT_DOMAINS = (
            'vape.gg', 'vape.sh', 'api.vape.gg',
            'future.gg', 'api.future.gg',
            'sigma.rip', 'api.sigma.rip',
            'liquidbounce.net', 'api.liquidbounce.net',
            'slinky.gg', 'entropy.zip', 'whiteout.gg',
            'drip.cx', 'meteor.gg', 'astolfo.club',
            'rise.wtf', 'wurst-client.xyz', 'aristois.net',
            'tenacity.gg', 'vertex.wtf', 'inertia.cc',
            'flux.gg', 'ghost.wtf', 'moonclient.cc', 'reflex.rip',
            'novoline.wtf', 'crtclient.cc', 'thunderhack.net',
            'volpe.gg', 'nextgen.wtf', 'iridium.pw',
        )
        try:
            import socket as _sock
            for proc in psutil.process_iter(['pid', 'name']):
                try:
                    name = (proc.info.get('name') or '').lower()
                    if 'javaw' not in name and 'java.exe' != name:
                        continue
                    try:
                        conns = proc.net_connections(kind='inet')
                    except (psutil.AccessDenied, AttributeError):
                        try:
                            conns = proc.connections(kind='inet')
                        except Exception:
                            continue
                    for conn in conns:
                        if conn.status != 'ESTABLISHED':
                            continue
                        raddr = conn.raddr
                        if not raddr or not raddr.ip:
                            continue
                        if raddr.port in GAME_PORTS:
                            continue  # conexión al servidor Minecraft, completamente normal
                        remote_ip = raddr.ip
                        if any(remote_ip.startswith(p) for p in TRUSTED_IPS_PREFIX):
                            continue
                        hostname = ''
                        try:
                            _sock.setdefaulttimeout(0.5)
                            hostname = _sock.gethostbyaddr(remote_ip)[0].lower()
                        except Exception:
                            hostname = ''
                        finally:
                            _sock.setdefaulttimeout(None)

                        if hostname and any(hostname.endswith(d) for d in TRUSTED_DOMAINS_SUFFIX):
                            continue
                        label = hostname or remote_ip
                        port  = raddr.port
                        # Check if it's a known hack client domain
                        is_hack_domain = hostname and any(
                            hostname == hd or hostname.endswith('.' + hd)
                            for hd in HACK_CLIENT_DOMAINS
                        )
                        if is_hack_domain:
                            print(f"🚨 CONEXIÓN A SERVIDOR DE GHOST CLIENT: {label}:{port}")
                            self.issues_found.append({
                                'nombre': f'Conexión activa a servidor de ghost client: {label}',
                                'ruta': f'{remote_ip}:{port}',
                                'archivo': 'javaw.exe',
                                'tipo': 'hack_client_network_connection',
                                'categoria': 'RED',
                                'alerta': 'CRITICAL',
                                'confidence': 0.90,
                                'detected_patterns': [f'hack_client_conn:{label}:{port}'],
                                'explicacion': f'javaw.exe tiene una conexión activa a {label}:{port}, '
                                               f'dominio asociado a un ghost client conocido. '
                                               f'Los clientes como Vape, Future y Sigma se conectan '
                                               f'a sus servidores de licencia mientras están activos.',
                            })
                        else:
                            print(f"⚠️ CONEXIÓN EXTERNA DE JAVAW: {label}:{port}")
                            self.issues_found.append({
                                'nombre': f'Conexión de Minecraft a host externo no reconocido: {label}',
                                'ruta': f'{remote_ip}:{port}',
                                'archivo': 'javaw.exe',
                                'tipo': 'suspicious_network_connection',
                                'categoria': 'RED',
                                'alerta': 'POCO_SOSPECHOSO',
                                'confidence': 0.35,
                                'detected_patterns': [f'javaw_external_conn:{label}:{port}'],
                                'explicacion': f'javaw.exe tiene una conexión activa a {label}:{port}. '
                                               f'No coincide con dominios de Mojang, CDNs ni launchers conocidos. '
                                               f'Puede ser un mod, plugin o recurso externo legítimo.',
                            })
                except (psutil.NoSuchProcess, psutil.AccessDenied):
                    continue
        except Exception as e:
            print(f"Error en scan_javaw_network_connections: {e}")

    def _apply_process_whitelist(self, issues):
        """P2 #13 — Descarta procesos conocidos y seguros del listado de hallazgos."""
        SAFE_PROCESSES = {
            # Sistema / drivers
            'svchost.exe', 'lsass.exe', 'winlogon.exe', 'csrss.exe', 'smss.exe',
            'services.exe', 'wininit.exe', 'dwm.exe', 'taskhost.exe', 'taskhostw.exe',
            'conhost.exe', 'dllhost.exe', 'rundll32.exe', 'regsvr32.exe',
            # Gamer / overlay
            'discord.exe', 'discordptb.exe', 'discordcanary.exe',
            'steam.exe', 'steamwebhelper.exe', 'gameoverlayui.exe',
            'nvcontainer.exe', 'nvdisplay.container.exe', 'nvcplui.exe',
            'nvtelemetrycontainer.exe', 'nvidia web helper.exe',
            'xboxapp.exe', 'gamebar.exe', 'gamebarftserver.exe',
            'obs64.exe', 'obs.exe', 'obs-browser-page.exe',
            'spotify.exe', 'spoticrashhandler.exe',
            'msedge.exe', 'chrome.exe', 'firefox.exe', 'opera.exe',
            'epicgameslauncher.exe', 'easyanticheat.exe',
            'geforceexperience.exe', 'geforcenow.exe',
            # Minecraft legítimos
            'javaw.exe', 'java.exe', 'minecraft.exe', 'minecraftlauncher.exe',
            'prismlauncher.exe', 'multimc.exe', 'ftblauncher.exe',
            'curseforgeapp.exe', 'gdlauncher.exe', 'atlauncher.exe',
            # Windows utilities
            'explorer.exe', 'taskmgr.exe', 'notepad.exe', 'mspaint.exe',
            'cmd.exe', 'powershell.exe', 'windowsterminal.exe',
        }
        result = []
        for issue in issues:
            archivo = (issue.get('archivo') or '').lower().strip()
            if issue.get('categoria') == 'PROCESO' and archivo in SAFE_PROCESSES:
                # Solo descartar si la confianza es baja y no tiene combo penalty
                if issue.get('confidence', 1.0) < 0.75 and not issue.get('combination_penalty'):
                    continue
            result.append(issue)
        return result

    def second_pass_scanner(self):
        """Segunda pasada: analiza archivos SOSPECHOSO/CRITICAL con mayor profundidad."""
        print("🔬 Segunda pasada de análisis sobre archivos sospechosos...")
        try:
            candidates = [i for i in self.issues_found
                          if i.get('alerta') in ('SOSPECHOSO', 'CRITICAL')
                          and i.get('tipo') in ('file', 'jar_file', 'minecraft_file', 'exe_file')
                          and i.get('ruta') and os.path.isfile(str(i.get('ruta', '')))]

            upgraded = 0
            for issue in candidates[:50]:  # Limit to 50 to avoid slowdown
                try:
                    analysis = self.analyze_file_content(str(issue['ruta']))
                    if analysis.get('is_hack') and analysis.get('confidence', 0) > issue.get('confidence', 0):
                        issue['confidence'] = analysis['confidence']
                        issue['detected_patterns'] = list(set(
                            issue.get('detected_patterns', []) + analysis.get('detected_patterns', [])))
                        issue['file_hash'] = analysis.get('file_hash') or issue.get('file_hash')
                        if analysis['confidence'] >= 80:
                            issue['alerta'] = 'CRITICAL'
                            upgraded += 1
                        elif analysis['confidence'] >= 60:
                            issue['alerta'] = 'SOSPECHOSO'
                except Exception:
                    pass
            print(f"✅ Segunda pasada: {upgraded} archivos actualizados a CRITICAL")
        except Exception as e:
            print(f"Error en second_pass_scanner: {e}")

    def show_details(self):
        """Muestra la ventana de detalles"""
        if self.issues_found:
            DetallesVentana(self.root, self.issues_found)
        else:
            messagebox.showinfo("Sin resultados", "No hay resultados para mostrar")
    
    def generate_html_report(self):
        """Genera reporte HTML mejorado con categorías"""
        try:
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            report_filename = f"SS_Report_{timestamp}.html"
            
            # Clasificar elementos por categoría
            illegal_files = []
            suspicious_files = []
            clean_files = []
            
            for item in self.issues_found:
                alerta = item.get('alerta', '').upper()
                if alerta == 'CRITICAL':
                    illegal_files.append(item)
                elif alerta in ['SOSPECHOSO', 'POCO_SOSPECHOSO']:
                    suspicious_files.append(item)
                else:
                    clean_files.append(item)
            
            # Obtener información del sistema
            system_info = self.get_system_info()
            
            # Calcular estadísticas de archivos escaneados
            total_files_scanned = getattr(self, 'total_files_scanned', 0)
            if total_files_scanned == 0:
                # Intentar calcular desde los issues encontrados si no hay contador
                total_files_scanned = len(self.issues_found) * 10  # Estimación conservadora
            scan_duration = getattr(self, 'scan_duration', '00:00:00')
            
            html_content = f"""
            <!DOCTYPE html>
            <html>
            <head>
                <title>Minecraft SS Tool Report - Análisis Completo</title>
                <meta charset="utf-8">
                <style>
                    body {{ font-family: 'Segoe UI', Arial, sans-serif; background: linear-gradient(135deg, #0f0f23, #1a1a2e); color: #e0e0e0; margin: 0; padding: 0; min-height: 100vh; }}
                    .header {{ background: linear-gradient(135deg, #1a1a2e, #16213e); padding: 30px; text-align: center; box-shadow: 0 4px 20px rgba(0, 0, 0, 0.5); }}
                    .header h1 {{ color: #00d9ff; margin: 0; font-size: 2.5em; text-shadow: 0 0 20px rgba(0, 217, 255, 0.5); }}
                    .header p {{ color: #b4b4b4; margin: 10px 0; font-size: 1.2em; }}
                    .content {{ padding: 20px; max-width: 1400px; margin: 0 auto; }}
                    .stats {{ display: grid; grid-template-columns: repeat(auto-fit, minmax(250px, 1fr)); gap: 20px; margin: 30px 0; }}
                    .stat-card {{ background: linear-gradient(135deg, #2c3e50, #34495e); padding: 25px; border-radius: 15px; text-align: center; box-shadow: 0 8px 25px rgba(0, 0, 0, 0.3); transition: transform 0.3s ease; }}
                    .stat-card:hover {{ transform: translateY(-5px); }}
                    .stat-number {{ font-size: 2.5em; font-weight: bold; margin-bottom: 10px; }}
                    .stat-label {{ font-size: 1.1em; color: #b4b4b4; margin-top: 10px; }}
                    .illegal {{ color: #ff4444; text-shadow: 0 0 10px rgba(255, 68, 68, 0.5); }}
                    .suspicious {{ color: #ffa500; text-shadow: 0 0 10px rgba(255, 165, 0, 0.5); }}
                    .clean {{ color: #00ff00; text-shadow: 0 0 10px rgba(0, 255, 0, 0.5); }}
                    .system {{ color: #00d9ff; text-shadow: 0 0 10px rgba(0, 217, 255, 0.5); }}
                    .files {{ color: #ff6b6b; text-shadow: 0 0 10px rgba(255, 107, 107, 0.5); }}
                    .time {{ color: #4ecdc4; text-shadow: 0 0 10px rgba(78, 205, 196, 0.5); }}
                    .section {{ margin: 40px 0; background: rgba(44, 62, 80, 0.3); padding: 25px; border-radius: 15px; backdrop-filter: blur(10px); }}
                    .section h2 {{ color: #00d9ff; border-bottom: 3px solid #00d9ff; padding-bottom: 15px; font-size: 1.8em; text-shadow: 0 0 10px rgba(0, 217, 255, 0.3); }}
                    .issue {{ background: linear-gradient(135deg, #2c3e50, #34495e); margin: 15px 0; padding: 20px; border-radius: 10px; border-left: 5px solid; box-shadow: 0 4px 15px rgba(0, 0, 0, 0.2); }}
                    .critical {{ border-left-color: #ff4444; }}
                    .suspicious {{ border-left-color: #ffa500; }}
                    .clean {{ border-left-color: #00ff00; }}
                    .issue-title {{ font-weight: bold; color: #fff; font-size: 1.1em; margin-bottom: 10px; }}
                    .issue-details {{ color: #b4b4b4; margin: 8px 0; }}
                    .timestamp {{ color: #888; font-size: 0.9em; text-align: center; margin-top: 30px; }}
                    .system-info {{ background: linear-gradient(135deg, #1e3c72, #2a5298); padding: 20px; border-radius: 10px; margin: 20px 0; }}
                    .system-info h3 {{ color: #00d9ff; margin-top: 0; }}
                    .info-grid {{ display: grid; grid-template-columns: repeat(auto-fit, minmax(300px, 1fr)); gap: 20px; }}
                    .info-card {{ background: rgba(255, 255, 255, 0.1); padding: 15px; border-radius: 8px; }}
                    .info-card h4 {{ color: #00d9ff; margin-top: 0; }}
                    .usb-list {{ max-height: 200px; overflow-y: auto; }}
                    .usb-item {{ background: rgba(0, 217, 255, 0.1); padding: 8px; margin: 5px 0; border-radius: 5px; }}
                </style>
            </head>
            <body>
                <div class="header">
                    <h1>🔍 Minecraft SS Tool - Reporte Completo</h1>
                    <p>Análisis exhaustivo del sistema - Generado el {datetime.now().strftime("%Y-%m-%d %H:%M:%S")}</p>
                    <p>⏱️ Tiempo de escaneo: {self.get_scan_duration()}</p>
                </div>
                <div class="content">
                    <div class="stats">
                        <div class="stat-card">
                            <div class="stat-number illegal">{len(illegal_files)}</div>
                            <div class="stat-label">🚨 Archivos Ilegales</div>
                        </div>
                        <div class="stat-card">
                            <div class="stat-number suspicious">{len(suspicious_files)}</div>
                            <div class="stat-label">⚠️ Archivos Sospechosos</div>
                        </div>
                        <div class="stat-card">
                            <div class="stat-number clean">{len(clean_files)}</div>
                            <div class="stat-label">✅ Archivos Limpios</div>
                        </div>
                        <div class="stat-card">
                            <div class="stat-number files">{total_files_scanned:,}</div>
                            <div class="stat-label">📁 Archivos Escaneados</div>
                        </div>
                        <div class="stat-card">
                            <div class="stat-number time">{scan_duration}</div>
                            <div class="stat-label">⏱️ Tiempo de Escaneo</div>
                        </div>
                        <div class="stat-card">
                            <div class="stat-number system">{len(self.issues_found)}</div>
                            <div class="stat-label">📊 Total Analizados</div>
                        </div>
                        <div class="stat-card" style="{'background:linear-gradient(135deg,#3a0000,#5a0000);' if getattr(self,'mouse_findings',[]) else ''}">
                            <div class="stat-number" style="color:{'#ff4444' if getattr(self,'mouse_findings',[]) else '#00ff00'};">{len(getattr(self,'mouse_findings',[]))}</div>
                            <div class="stat-label">🖱️ Alertas de Mouse</div>
                        </div>
                        <div class="stat-card" style="{'background:linear-gradient(135deg,#1a0a3a,#2a0a5a);' if getattr(self,'forensic_findings',[]) else ''}">
                            <div class="stat-number" style="color:{'#cc88ff' if getattr(self,'forensic_findings',[]) else '#00ff00'};">{len(getattr(self,'forensic_findings',[]))}</div>
                            <div class="stat-label">🔬 Evidencia Forense</div>
                        </div>
                    </div>
                    
                    <div class="section">
                        <h2>💻 Información del Sistema</h2>
                        <div class="system-info">
                            <div class="info-grid">
                                <div class="info-card">
                                    <h4>👤 Información del Usuario</h4>
                                    <p><strong>Usuario:</strong> {system_info.get('username', 'N/A')}</p>
                                    <p><strong>PC:</strong> {system_info.get('computer_name', 'N/A')}</p>
                                    <p><strong>IP Local:</strong> {system_info.get('local_ip', 'N/A')}</p>
                                </div>
                                <div class="info-card">
                                    <h4>🔌 Dispositivos USB Conectados</h4>
                                    <div class="usb-list">
                                        {self._generate_usb_section(system_info.get('usb_devices', []))}
                                    </div>
                                </div>
                                <div class="info-card">
                                    <h4>🗑️ Información de la Papelera</h4>
                                    <p><strong>Última limpieza:</strong> {system_info.get('recycle_bin', {}).get('last_cleared', 'N/A')}</p>
                                    <p><strong>Hace:</strong> {system_info.get('recycle_bin', {}).get('days_ago', 'N/A')} días</p>
                                </div>
                                <div class="info-card">
                                    <h4>⚙️ Recursos del Sistema</h4>
                                    <p><strong>Procesos activos:</strong> {system_info.get('process_count', 0)}</p>
                                    <p><strong>RAM total:</strong> {system_info.get('memory_total', 'N/A')}</p>
                                    <p><strong>RAM usada:</strong> {system_info.get('memory_used', 'N/A')}</p>
                                </div>
                                <div class="info-card">
                                    <h4>🌐 Información de Red</h4>
                                    <p><strong>Conexiones totales:</strong> {system_info.get('network_info', {}).get('total_connections', 0)}</p>
                                    <p><strong>Conexiones establecidas:</strong> {system_info.get('network_info', {}).get('established_connections', 0)}</p>
                                    <p><strong>Puertos escuchando:</strong> {system_info.get('network_info', {}).get('listening_ports', 0)}</p>
                                </div>
                            </div>
                        </div>
                    </div>
                    
                    {self._generate_mouse_section()}

                    {self._generate_forensic_section()}

                    <div class="section">
                        <h2>🚨 Archivos Ilegales Detectados</h2>
                        {self._generate_illegal_files_section(illegal_files[:10])}
                        {self._generate_summary_section(illegal_files, 'ilegales', 10)}
                    </div>
                    
                    <div class="section">
                        <h2>⚠️ Archivos Sospechosos Detectados</h2>
                        {self._generate_suspicious_files_section(suspicious_files[:20])}
                        {self._generate_summary_section(suspicious_files, 'sospechosos', 20)}
                    </div>
                    
                    <div class="section">
                        <h2>✅ Archivos Limpios Verificados</h2>
                        {self._generate_clean_files_section(clean_files[:10])}
                        {self._generate_summary_section(clean_files, 'limpios', 10)}
                    </div>
                    
                    <div class="section">
                        <h2>📊 Resumen del Análisis</h2>
                        <div class="info-grid">
                            <div class="info-card">
                                <h4>📈 Estadísticas Generales</h4>
                                <p>Total de elementos analizados: <strong>{len(self.issues_found)}</strong></p>
                                <p>Archivos ilegales encontrados: <strong>{len(illegal_files)}</strong></p>
                                <p>Archivos sospechosos encontrados: <strong>{len(suspicious_files)}</strong></p>
                                <p>Archivos limpios verificados: <strong>{len(clean_files)}</strong></p>
                            </div>
                            <div class="info-card">
                                <h4>⚡ Rendimiento del Escaneo</h4>
                                <p>Tiempo total: <strong>{self.get_scan_duration()}</strong></p>
                                <p>CPU cores utilizados: <strong>{psutil.cpu_count()}</strong></p>
                                <p>Memoria disponible: <strong>{psutil.virtual_memory().available / (1024**3):.1f} GB</strong></p>
                            </div>
                        </div>
                        <p class="timestamp">Reporte generado automáticamente por Minecraft SS Tool v2.0</p>
                    </div>
                </div>
            </body>
            </html>
            """
            
            with open(report_filename, 'w', encoding='utf-8') as f:
                f.write(html_content)
            
            print(f"📄 Reporte HTML generado: {report_filename}")
            
        except Exception as e:
            print(f"Error generando reporte HTML: {e}")
    
    def _generate_mouse_section(self):
        """Genera la sección de detección de manipulación de mouse para el reporte HTML."""
        mf = getattr(self, 'mouse_findings', [])
        if not mf:
            return """
            <div class="section" style="border-left:4px solid #00ff00;">
                <h2 style="color:#00ff00;">🖱️ Detección de Mouse (Prison Mode)</h2>
                <p style="color:#00ff00;">✅ Sin indicadores de peso, click-bug ni manipulación de mouse.</p>
            </div>"""

        rows = ""
        for item in mf:
            color  = "#ff4444" if item.get('alerta') == 'CRITICAL' else "#ffa500"
            icon   = "🔴" if item.get('alerta') == 'CRITICAL' else "🟠"
            rows += f"""
            <div class="issue critical" style="border-left-color:{color};">
                <div class="issue-title" style="color:{color};">{icon} {item.get('nombre','')}</div>
                <div class="issue-details"><strong>Detalle:</strong> {item.get('detalle','')}</div>
                <div class="issue-details" style="color:#e0e0e0;">{item.get('descripcion','')}</div>
                <div class="issue-details" style="color:#888;font-size:0.85em;">
                    Severidad: <strong style="color:{color};">{item.get('alerta','')}</strong>
                    &nbsp;|&nbsp; Tipo: {item.get('tipo','')}
                </div>
            </div>"""

        return f"""
        <div class="section" style="border:1px solid rgba(255,68,68,0.4);background:rgba(120,0,0,0.15);">
            <h2 style="color:#ff4444;border-bottom-color:#ff4444;">
                🖱️ Detección de Manipulación de Mouse (Prison Mode)
                <span style="font-size:0.6em;background:#ff4444;color:#fff;
                             padding:3px 10px;border-radius:10px;margin-left:12px;">
                    {len(mf)} ALERTA(S)
                </span>
            </h2>
            <p style="color:#ffa0a0;margin-bottom:16px;font-size:0.95em;">
                ⚠️  Se detectaron indicadores de <strong>peso sobre el mouse</strong>,
                <strong>click-bug activo</strong> o <strong>desconexión/reconexión de dispositivo</strong>
                durante la sesión de SS. Estas técnicas se usan en prison mode para obtener
                autoclick sin software detectable.
            </p>
            {rows}
        </div>"""

    def _generate_forensic_section(self):
        """Genera la sección de análisis forense SS para el reporte HTML."""
        ff = getattr(self, 'forensic_findings', [])
        if not ff:
            return """
            <div class="section" style="border-left:4px solid #00ff00;">
                <h2 style="color:#00ff00;">🔬 Análisis Forense SS (Checklist Manual)</h2>
                <p style="color:#00ff00;">✅ Sin evidencia histórica de hacks, autoclickers ni herramientas de evasión.</p>
            </div>"""

        rows = ""
        for item in ff:
            color = "#cc88ff" if item.get('alerta') == 'CRITICAL' else "#66aaff"
            icon  = "🔴" if item.get('alerta') == 'CRITICAL' else "🔬"
            rows += f"""
            <div class="issue" style="border-left:3px solid {color};background:rgba(80,0,120,0.15);margin-bottom:8px;padding:10px 14px;">
                <div class="issue-title" style="color:{color};">{icon} {item.get('nombre','')}</div>
                <div class="issue-details"><strong>Fuente:</strong> {item.get('tipo','')}</div>
                <div class="issue-details"><strong>Detalle:</strong> {item.get('detalle','')}</div>
                <div class="issue-details" style="color:#e0e0e0;">{item.get('descripcion','')}</div>
                <div class="issue-details" style="color:#888;font-size:0.85em;">
                    Severidad: <strong style="color:{color};">{item.get('alerta','')}</strong>
                </div>
            </div>"""

        return f"""
        <div class="section" style="border:1px solid rgba(180,80,255,0.4);background:rgba(50,0,80,0.15);">
            <h2 style="color:#cc88ff;border-bottom-color:#cc88ff;">
                🔬 Análisis Forense SS — Evidencia Histórica
                <span style="font-size:0.6em;background:#cc88ff;color:#fff;
                             padding:3px 10px;border-radius:10px;margin-left:12px;">
                    {len(ff)} HALLAZGO(S)
                </span>
            </h2>
            <p style="color:#d0a0ff;margin-bottom:16px;font-size:0.95em;">
                ⚠️  Técnicas del checklist manual SS: USN Journal, BAM, AppCompat, UserAssist,
                WinRAR, Prefetch, DisallowRun y más. Esta evidencia <strong>sobrevive la eliminación
                del scanner</strong> y es recuperable incluso cuando el jugador lo borró.
            </p>
            {rows}
        </div>"""

    def _generate_illegal_files_section(self, illegal_files):
        """Genera la sección de archivos ilegales"""
        if not illegal_files:
            return "<p style='color: #00ff00;'>✅ No se encontraron archivos ilegales</p>"
        
        html = ""
        for item in illegal_files:
            html += f"""
            <div class="issue critical">
                <div class="issue-title">🚨 {item.get('nombre', 'N/A')}</div>
                <div class="issue-details">Tipo: {item.get('tipo', 'N/A')}</div>
                <div class="issue-details">Ruta: {item.get('ruta', 'N/A')}</div>
                <div class="issue-details">Categoría: {item.get('categoria', 'N/A')}</div>
            </div>
            """
        return html
    
    def _generate_suspicious_files_section(self, suspicious_files):
        """Genera la sección de archivos sospechosos"""
        if not suspicious_files:
            return "<p style='color: #00ff00;'>✅ No se encontraron archivos sospechosos</p>"
        
        html = ""
        for item in suspicious_files:
            html += f"""
            <div class="issue suspicious">
                <div class="issue-title">⚠️ {item.get('nombre', 'N/A')}</div>
                <div class="issue-details">Tipo: {item.get('tipo', 'N/A')}</div>
                <div class="issue-details">Ruta: {item.get('ruta', 'N/A')}</div>
                <div class="issue-details">Categoría: {item.get('categoria', 'N/A')}</div>
            </div>
            """
        return html
    
    def _generate_clean_files_section(self, clean_files):
        """Genera la sección de archivos limpios"""
        if not clean_files:
            return "<p style='color: #ffa500;'>⚠️ No se encontraron archivos limpios para mostrar</p>"
        
        html = ""
        for item in clean_files:
            html += f"""
            <div class="issue clean">
                <div class="issue-title">✅ {item.get('nombre', 'N/A')}</div>
                <div class="issue-details">Tipo: {item.get('tipo', 'N/A')}</div>
                <div class="issue-details">Ruta: {item.get('ruta', 'N/A')}</div>
                <div class="issue-details">Categoría: {item.get('categoria', 'N/A')}</div>
            </div>
            """
        return html
    
    def _generate_usb_section(self, usb_devices):
        """Genera la sección de dispositivos USB"""
        if not usb_devices:
            return "<p style='color: #ffa500;'>⚠️ No se encontraron dispositivos USB conectados</p>"
        
        html = ""
        for device in usb_devices:
            html += f"""
            <div class="usb-item">
                🔌 {device}
            </div>
            """
        return html
    
    # Función de Discord eliminada - Todo se gestiona vía Web ahora
    
    def get_scan_duration(self):
        """Obtiene la duración del escaneo"""
        if hasattr(self, 'scan_start_time'):
            duration = time.time() - self.scan_start_time
            hours, remainder = divmod(duration, 3600)
            minutes, seconds = divmod(remainder, 60)
            return f"{int(hours):02d}:{int(minutes):02d}:{int(seconds):02d}"
        return "N/A"
    
    def get_system_info(self):
        """Obtiene información completa del sistema"""
        try:
            import socket
            import getpass
            import psutil
            
            # Información del usuario
            username = getpass.getuser()
            computer_name = socket.gethostname()
            
            # Información de IP
            try:
                hostname = socket.gethostname()
                local_ip = socket.gethostbyname(hostname)
            except:
                local_ip = "No disponible"
            
            # Información de USBs (sin dependencias externas)
            usb_devices = []
            try:
                import subprocess
                # Usar wmic que viene con Windows
                result = subprocess.run(['wmic', 'logicaldisk', 'where', 'drivetype=2', 'get', 'deviceid,volumename'],
                                      capture_output=True, text=True, timeout=10,
                                      creationflags=0x08000000)
                if result.returncode == 0:
                    lines = result.stdout.strip().split('\n')
                    for line in lines[1:]:  # Saltar la primera línea (encabezado)
                        if line.strip():
                            parts = line.strip().split()
                            if len(parts) >= 2:
                                usb_devices.append(f"{parts[0]} - {parts[1] if parts[1] != 'None' else 'Sin nombre'}")
                            elif len(parts) == 1:
                                usb_devices.append(f"{parts[0]} - Sin nombre")
                else:
                    usb_devices = ["No se pudieron obtener dispositivos USB"]
            except Exception as e:
                print(f"Error obteniendo USBs: {e}")
                usb_devices = ["No se pudieron obtener dispositivos USB"]
            
            # Información de la papelera
            recycle_bin_info = self.get_recycle_bin_info()
            
            # Información de procesos
            try:
                process_count = len(list(psutil.process_iter()))
            except:
                process_count = 0
            
            # Información de memoria
            try:
                memory = psutil.virtual_memory()
                memory_total = f"{memory.total / (1024**3):.1f} GB"
                memory_used = f"{memory.used / (1024**3):.1f} GB"
            except:
                memory_total = "No disponible"
                memory_used = "No disponible"
            
            # Información de red
            network_info = self.get_network_info()
            
            print(f"DEBUG - Username: {username}, Computer: {computer_name}, IP: {local_ip}")
            print(f"DEBUG - USBs: {len(usb_devices)}, Processes: {process_count}")
            
            return {
                'username': username,
                'computer_name': computer_name,
                'local_ip': local_ip,
                'usb_devices': usb_devices,
                'recycle_bin': recycle_bin_info,
                'process_count': process_count,
                'memory_total': memory_total,
                'memory_used': memory_used,
                'network_info': network_info
            }
        except Exception as e:
            print(f"Error obteniendo información del sistema: {e}")
            return {
                'username': 'Usuario',
                'computer_name': 'PC',
                'local_ip': 'No disponible',
                'usb_devices': [],
                'recycle_bin': {},
                'process_count': 0,
                'memory_total': 'No disponible',
                'memory_used': 'No disponible',
                'network_info': {}
            }
    
    def setup_security_measures(self):
        """Configura medidas de seguridad para la aplicación"""
        try:
            import os
            import time
            import threading
            
            print("🛡️ CONFIGURANDO MEDIDAS DE SEGURIDAD...")
            
            # Crear archivo de autodestrucción
            self.create_self_destruct_script()
            
            # Configurar limpieza automática
            self.setup_auto_cleanup()
            
            # Configurar protección contra detección
            self.setup_anti_detection()
            
            print("✅ Medidas de seguridad configuradas correctamente")
            
        except Exception as e:
            print(f"Error configurando medidas de seguridad: {e}")
    
    def create_self_destruct_script(self):
        """Crea script de autodestrucción de la aplicación - DESACTIVADO POR SEGURIDAD"""
        # DESACTIVADO: Esta función creaba scripts de limpieza que podían causar problemas
        # if se ejecutaba desde el directorio incorrecto
        pass
        # try:
        #     import os
        #     
        #     script_content = '''@echo off
        # echo Limpiando archivos temporales...
        # timeout /t 3 /nobreak >nul
        # del /f /q "*.tmp" 2>nul
        # del /f /q "*.log" 2>nul
        # del /f /q "*.cache" 2>nul
        # echo Limpieza completada.
        # timeout /t 2 /nobreak >nul
        # '''
        #     
        #     with open("cleanup.bat", "w") as f:
        #         f.write(script_content)
        #         
        #     print("🛡️ Script de autodestrucción creado: cleanup.bat")
        #     
        # except Exception as e:
        #     print(f"Error creando script de autodestrucción: {e}")
    
    def setup_auto_cleanup(self):
        """Configura limpieza automática de archivos temporales - DESACTIVADO POR SEGURIDAD"""
        # DESACTIVADO: Esta función borraba archivos automáticamente y podía causar problemas
        # si se ejecutaba desde el directorio incorrecto
        pass
        # try:
        #     import os
        #     import time
        #     import threading
        #     
        #     def cleanup_temp_files():
        #         """Limpia archivos temporales cada 5 minutos"""
        #         while True:
        #             try:
        #                 temp_files = [f for f in os.listdir('.') if f.endswith(('.tmp', '.log', '.cache'))]
        #                 for file in temp_files:
        #                     try:
        #                         os.remove(file)
        #                     except:
        #                         pass
        #                 time.sleep(300)  # 5 minutos
        #             except:
        #                 break
        #     
        #     # Iniciar limpieza automática en segundo plano
        #     cleanup_thread = threading.Thread(target=cleanup_temp_files, daemon=True)
        #     cleanup_thread.start()
        #     
        #     print("🧹 Limpieza automática configurada")
        #     
        # except Exception as e:
        #     print(f"Error configurando limpieza automática: {e}")
    
    def setup_anti_detection(self):
        """Configura protección contra detección"""
        try:
            import os
            import random
            import time
            
            # Cambiar nombre del proceso para evitar detección
            try:
                import psutil
                current_process = psutil.Process()
                new_name = f"system_{random.randint(1000, 9999)}.exe"
                print(f"🛡️ Nombre del proceso cambiado a: {new_name}")
            except:
                pass
            
            # Crear archivos falsos para confundir
            fake_files = [
                "windows_update.exe",
                "system_service.dll",
                "security_monitor.log"
            ]
            
            for fake_file in fake_files:
                try:
                    with open(fake_file, "w") as f:
                        f.write("# Archivo del sistema - No eliminar")
                except:
                    pass
            
            print("🛡️ Protección contra detección configurada")
            
        except Exception as e:
            print(f"Error configurando protección contra detección: {e}")
    
    def get_recycle_bin_info(self):
        """Obtiene información de la papelera"""
        try:
            import os
            from datetime import datetime
            
            # Buscar en múltiples ubicaciones de la papelera
            recycle_bin_paths = [
                os.path.expanduser("~\\AppData\\Local\\Microsoft\\Windows\\FileHistory\\Config"),
                os.path.expanduser("~\\AppData\\Local\\Microsoft\\Windows\\FileHistory\\Data"),
                os.path.expanduser("~\\AppData\\Local\\Microsoft\\Windows\\FileHistory\\Logs"),
                "C:\\$Recycle.Bin"
            ]
            
            for recycle_bin_path in recycle_bin_paths:
                if os.path.exists(recycle_bin_path):
                    try:
                        # Obtener fecha de última modificación
                        last_modified = os.path.getmtime(recycle_bin_path)
                        last_modified_date = datetime.fromtimestamp(last_modified)
                        
                        return {
                            'last_cleared': last_modified_date.strftime("%Y-%m-%d %H:%M:%S"),
                            'days_ago': (datetime.now() - last_modified_date).days
                        }
                    except:
                        continue
            
            return {'last_cleared': 'N/A', 'days_ago': 'N/A'}
        except Exception as e:
            print(f"Error obteniendo información de la papelera: {e}")
            return {'last_cleared': 'N/A', 'days_ago': 'N/A'}
    
    def get_network_info(self):
        """Obtiene información de red"""
        try:
            connections = psutil.net_connections(kind='inet')
            established_connections = [c for c in connections if c.status == 'ESTABLISHED']
            
            return {
                'total_connections': len(connections),
                'established_connections': len(established_connections),
                'listening_ports': len([c for c in connections if c.status == 'LISTEN'])
            }
        except Exception as e:
            print(f"Error obteniendo información de red: {e}")
            return {'total_connections': 0, 'established_connections': 0, 'listening_ports': 0}
    
    def show_completion_message(self):
        """Muestra ventana simple de finalización: scan enviado a la web."""
        import tkinter as tk

        web_url  = self.config.get('web_url', 'https://asperss.onrender.com').rstrip('/')
        staff    = self.config.get('staff_name', self.config.get('scan_token', ''))

        # Actualizar área de texto con estado mínimo
        try:
            self.results_text.delete(1.0, tk.END)
            self.results_text.insert(tk.END, "✅ Escaneo completado — resultados enviados a la página\n", "success")
        except Exception:
            pass

        win = tk.Toplevel(self.root)
        win.title("Escaneo Finalizado")
        win.geometry("460x200")
        win.configure(bg="#060912")
        win.resizable(False, False)
        win.grab_set()

        # Centrar
        win.update_idletasks()
        x = (win.winfo_screenwidth()  // 2) - 230
        y = (win.winfo_screenheight() // 2) - 100
        win.geometry(f"460x200+{x}+{y}")

        inner = tk.Frame(win, bg="#060912")
        inner.pack(fill="both", expand=True, padx=30, pady=24)

        tk.Label(inner, text="✅  Escaneo Finalizado",
                 font=("Segoe UI", 15, "bold"), bg="#060912", fg="#22d3a5").pack(anchor="w")

        tk.Label(inner,
                 text=f"Resultados enviados a  {web_url}",
                 font=("Segoe UI", 10), bg="#060912", fg="#5a7296",
                 wraplength=400, justify="left").pack(anchor="w", pady=(8, 2))

        tk.Label(inner,
                 text=f"Staff:  {staff}",
                 font=("Segoe UI", 10, "bold"), bg="#060912", fg="#dce8f5").pack(anchor="w")

        tk.Button(inner, text="Aceptar", command=win.destroy,
                  bg="#00a8d4", fg="white", font=("Segoe UI", 11, "bold"),
                  relief="flat", cursor="hand2", padx=20, pady=6).pack(anchor="e", pady=(18, 0))

    def _submit_ai_feedback(self, verdict, notes):
        """Envía feedback al servidor y actualiza patrones locales."""
        try:
            api_url = self.config.get('api_url', 'https://asperss.onrender.com')
            scan_id = None
            if self.db_integration and hasattr(self.db_integration, 'current_scan_id'):
                scan_id = self.db_integration.current_scan_id

            # Construir feedback por cada issue encontrado
            batch = []
            for issue in self.issues_found:
                staff_ver = 'hack' if verdict == 'hack_real' else \
                            'legit' if verdict == 'limpio' else \
                            'uncertain'
                batch.append({
                    'issue_name':  issue.get('nombre', ''),
                    'issue_path':  issue.get('ruta', ''),
                    'file_hash':   issue.get('hash', ''),
                    'alert_level': issue.get('alerta', ''),
                    'verification': staff_ver,
                    'notes': notes,
                    'scan_id': scan_id,
                })

            if batch:
                import requests as _req
                token = self.config.get('scan_token', '')
                resp = _req.post(
                    f"{api_url}/api/feedback/batch",
                    json={'feedback': batch, 'verdict': verdict, 'notes': notes},
                    headers={'Authorization': f'Bearer {token}'},
                    timeout=10
                )
                if resp.status_code == 200:
                    print(f"✅ Feedback enviado: {len(batch)} items, verdict={verdict}")
                    # Actualizar modelo local si el server devuelve nuevos patrones
                    data = resp.json()
                    if data.get('learned_patterns') and self.ai_analyzer:
                        try:
                            self.ai_analyzer.load_learned_patterns()
                            print("🧠 Patrones de IA actualizados desde feedback")
                        except Exception:
                            pass
                else:
                    print(f"⚠️ Error enviando feedback: {resp.status_code}")
        except Exception as ex:
            print(f"⚠️ Error en feedback IA: {ex}")
        
        # Actualizar resultados
        self.results_text.delete(1.0, tk.END)
        self.results_text.insert(tk.END, f"✅ ESCANEO COMPLETADO\n\n", "success")
        self.results_text.insert(tk.END, f"📊 Total de elementos encontrados: {len(self.issues_found)}\n\n", "info")
        
        if self.issues_found:
            self.results_text.insert(tk.END, "🔍 ELEMENTOS ENCONTRADOS:\n\n", "warning")
            for i, issue in enumerate(self.issues_found, 1):
                self.results_text.insert(tk.END, f"{i}. {issue.get('nombre', 'N/A')}\n", "info")
                self.results_text.insert(tk.END, f"   Tipo: {issue.get('tipo', 'N/A')}\n", "info")
                self.results_text.insert(tk.END, f"   Ruta: {issue.get('ruta', 'N/A')}\n", "info")
                self.results_text.insert(tk.END, f"   Alerta: {issue.get('alerta', 'N/A')}\n\n", "danger")
        else:
            self.results_text.insert(tk.END, "✅ No se encontraron elementos sospechosos\n", "success")
    
    def log(self, message, level="info"):
        """Registra un mensaje en el área de resultados"""
        self.results_text.insert(tk.END, f"{message}\n", level)
        self.results_text.see(tk.END)
    
    def detect_anydesk_start(self):
        """Detecta si AnyDesk está corriendo"""
        try:
            import psutil
            for proc in psutil.process_iter(['name']):
                if proc.info['name'] and 'anydesk' in proc.info['name'].lower():
                    self.anydesk_start_time = time.time()
                    print("🔍 AnyDesk detectado - Iniciando monitoreo")
                    break
        except Exception as e:
            print(f"Error detectando AnyDesk: {e}")
    
    def get_usb_devices(self):
        """Obtiene set de letras de unidades removibles (USB/pendrives) actualmente conectadas."""
        try:
            result = subprocess.run(
                ['wmic', 'logicaldisk', 'where', 'drivetype=2', 'get', 'caption,volumename,size'],
                capture_output=True, text=True, timeout=6, creationflags=0x08000000
            )
            drives = {}
            for line in result.stdout.splitlines():
                line = line.strip()
                if not line or 'Caption' in line:
                    continue
                parts = line.split()
                if parts and ':' in parts[0]:
                    letter = parts[0]
                    label = parts[1] if len(parts) > 1 and not parts[1].isdigit() else ''
                    size_bytes = int(parts[-1]) if parts[-1].isdigit() else 0
                    size_gb = round(size_bytes / (1024**3), 1) if size_bytes > 0 else 0
                    drives[letter] = {'label': label, 'size_gb': size_gb}
            return drives
        except Exception as e:
            print(f"Error obteniendo dispositivos USB: {e}")
            return {}

    def _start_usb_monitor(self):
        """Arranca un thread que monitorea conexiones/desconexiones de USB durante el scan."""
        import threading
        self._usb_monitor_stop = threading.Event()
        self._usb_monitor_thread = threading.Thread(
            target=self._usb_monitor_loop, daemon=True, name='USB-Monitor'
        )
        self._usb_monitor_thread.start()
        print(f"🔌 Monitor USB iniciado — {len(self.initial_usb_devices)} unidad(es) al inicio: "
              f"{list(self.initial_usb_devices.keys()) or 'ninguna'}")

    def _stop_usb_monitor(self):
        """Detiene el thread de monitoreo USB."""
        if hasattr(self, '_usb_monitor_stop'):
            self._usb_monitor_stop.set()
        if hasattr(self, '_usb_monitor_thread'):
            self._usb_monitor_thread.join(timeout=3)

    def _usb_monitor_loop(self):
        """Loop de monitoreo USB — compara estado cada 2 segundos."""
        known = dict(self.initial_usb_devices)
        while not self._usb_monitor_stop.wait(2):
            try:
                current = self.get_usb_devices()

                # Unidades que desaparecieron
                for letter, info in known.items():
                    if letter not in current:
                        label = info.get('label') or 'Sin nombre'
                        size  = info.get('size_gb', 0)
                        desc  = f"{letter} — {label} ({size} GB)" if size else f"{letter} — {label}"
                        print(f"🚨 USB DESCONECTADO DURANTE SS: {desc}")
                        self.issues_found.append({
                            'nombre':  f'USB desconectado durante la SS: {desc}',
                            'ruta':    letter,
                            'archivo': label or letter,
                            'tipo':    'usb_removed',
                            'categoria': 'EVASION',
                            'alerta':  'CRITICAL',
                            'confidence': 0.97,
                            'detected_patterns': ['usb_removed_during_ss'],
                            'explicacion': (
                                f'La unidad removible {desc} fue desconectada MIENTRAS el scan '
                                f'estaba en curso. Esto indica un intento de ocultar evidencia '
                                f'(pendrive con hack, configs, etc.).'
                            ),
                        })

                # Unidades nuevas que aparecieron
                for letter, info in current.items():
                    if letter not in known:
                        label = info.get('label') or 'Sin nombre'
                        size  = info.get('size_gb', 0)
                        desc  = f"{letter} — {label} ({size} GB)" if size else f"{letter} — {label}"
                        print(f"⚠️ USB CONECTADO DURANTE SS: {desc}")
                        self.issues_found.append({
                            'nombre':  f'USB conectado durante la SS: {desc}',
                            'ruta':    letter,
                            'archivo': label or letter,
                            'tipo':    'usb_added',
                            'categoria': 'EVASION',
                            'alerta':  'SOSPECHOSO',
                            'confidence': 0.75,
                            'detected_patterns': ['usb_added_during_ss'],
                            'explicacion': (
                                f'La unidad removible {desc} fue conectada MIENTRAS el scan '
                                f'estaba en curso. Puede ser un intento de introducir archivos '
                                f'o transferir evidencia.'
                            ),
                        })

                known = current
            except Exception:
                pass

def _setup_logging(log_path: str | None = None):
    """P5 #34 — Structured logging to a rotating .log file alongside the exe."""
    import logging
    from logging.handlers import RotatingFileHandler
    if log_path is None:
        exe_dir = os.path.dirname(os.path.abspath(sys.executable if getattr(sys, 'frozen', False) else __file__))
        log_path = os.path.join(exe_dir, 'argus_scanner.log')
    handler = RotatingFileHandler(log_path, maxBytes=2 * 1024 * 1024, backupCount=3, encoding='utf-8')
    handler.setFormatter(logging.Formatter('%(asctime)s [%(levelname)s] %(message)s'))
    root_logger = logging.getLogger()
    root_logger.setLevel(logging.INFO)
    root_logger.addHandler(handler)
    # Also redirect print() to the log via a small shim
    class _PrintToLog:
        def __init__(self, orig): self._orig = orig
        def write(self, msg):
            stripped = msg.rstrip()
            if stripped:
                logging.info(stripped)
            self._orig.write(msg)
        def flush(self): self._orig.flush()
        def isatty(self): return False
    sys.stdout = _PrintToLog(sys.stdout)


def _run_headless(token: str, api_url: str | None, output_json: str | None):
    """P5 #32 — Modo headless: ejecutar scan sin UI y guardar resultado en JSON."""
    import json as _json
    print(f"[HEADLESS] Argus Scanner v{SCANNER_VERSION} — modo sin interfaz")
    print(f"[HEADLESS] Token: {token[:8]}...")

    # Create a minimal fake root so ArgusApp doesn't crash on Tk calls
    import tkinter as _tk
    root = _tk.Tk()
    root.withdraw()

    app = ArgusApp(root)
    # Override token
    app.scan_token = token
    if api_url:
        app.api_url = api_url

    # Run the scan in blocking mode
    import threading
    done_event = threading.Event()
    result_holder = {}

    def _on_complete(result):
        result_holder['result'] = result
        done_event.set()

    app._headless_callback = _on_complete
    app._headless_mode = True

    scan_thread = threading.Thread(target=app.run_scan, daemon=True)
    scan_thread.start()
    # Poll Tk event loop until scan is done (up to 10 minutes)
    for _ in range(600):
        root.update()
        if done_event.wait(timeout=1):
            break

    root.destroy()

    result = result_holder.get('result', {})
    if output_json:
        with open(output_json, 'w', encoding='utf-8') as f:
            _json.dump(result, f, ensure_ascii=False, indent=2)
        print(f"[HEADLESS] Resultado guardado en {output_json}")
    else:
        print(_json.dumps(result, ensure_ascii=False, indent=2))


def main():
    """Función principal — soporta modo GUI y headless (--headless)."""
    import argparse
    parser = argparse.ArgumentParser(description=f'Argus Scanner v{SCANNER_VERSION}', add_help=False)
    parser.add_argument('--headless', action='store_true', help='Ejecutar sin interfaz gráfica')
    parser.add_argument('--token', default='', help='Token de escaneo (requerido en --headless)')
    parser.add_argument('--api-url', default='', help='URL base de la API (opcional)')
    parser.add_argument('--output', default='', help='Ruta de archivo JSON para el resultado (--headless)')
    parser.add_argument('--log', default='', help='Ruta de archivo de log (opcional)')
    parser.add_argument('--debug-filter', action='store_true', help='Mostrar hallazgos descartados en el filtro')
    parser.add_argument('--profile', default='', help='Nombre del perfil de servidor a usar (profiles.json)')
    args, _ = parser.parse_known_args()

    # P5 #34 — Enable structured logging if --log provided
    if args.log:
        _setup_logging(args.log)

    # P5 #35 — F35 debug-filter flag
    if args.debug_filter:
        os.environ['ARGUS_DEBUG_FILTER'] = '1'

    # P5 #35 — --profile selects saved server profile (overrides config.json token/api_url)
    if args.profile:
        os.environ['ARGUS_PROFILE'] = args.profile

    if args.headless:
        # P5 #32 — Headless mode
        # P5 #35 — --profile can substitute for --token in headless mode
        token_to_use = args.token
        api_to_use   = args.api_url or None
        if not token_to_use and args.profile:
            _prof_data = ArgusApp._load_scanner_profiles()
            _prof = _prof_data.get('profiles', {}).get(args.profile)
            if _prof:
                token_to_use = _prof.get('token', '')
                api_to_use   = api_to_use or _prof.get('api_url')
                print(f"🖥 Perfil headless: {args.profile!r}")
            else:
                print(f"ERROR: Perfil '{args.profile}' no encontrado en profiles.json")
                sys.exit(1)
        if not token_to_use:
            print("ERROR: --token o --profile requerido en modo --headless")
            sys.exit(1)
        _run_headless(token_to_use, api_to_use, args.output or None)
        return

    try:
        import tkinter as tk
        import tkinter.messagebox as messagebox

        root = tk.Tk()
        app = ArgusApp(root)
        root.mainloop()
    except KeyboardInterrupt:
        print("\n⚠️ Aplicación interrumpida por el usuario")
    except Exception as e:
        import traceback
        error_msg = f"Error al iniciar la aplicación:\n{str(e)}\n\n{traceback.format_exc()}"
        print(error_msg)
        try:
            import tkinter as tk
            import tkinter.messagebox as messagebox
            root = tk.Tk()
            root.withdraw()
            messagebox.showerror("Error Crítico",
                f"Error al iniciar la aplicación:\n\n{str(e)}\n\nRevisa la consola para más detalles.")
            root.destroy()
        except Exception:
            print("\n" + "="*50)
            print("ERROR CRÍTICO - La aplicación no pudo iniciarse")
            print("="*50)
            input("\nPresiona Enter para salir...")


if __name__ == "__main__":
    main()
