"""Filtros de falsos positivos extraidos de main.py (v1.8+)."""
from __future__ import annotations

import os
import sys

try:
    from forensic_match import match_hack_stem as _match_hack_stem, STRONG_STEMS as _STRONG_STEMS
    from config.hack_signatures import stem_in_filename as _stem_in_filename
except Exception:  # pragma: no cover - fallback si faltan los módulos
    _match_hack_stem = None
    _STRONG_STEMS = ()

    def _stem_in_filename(stem, name):
        return bool(stem) and stem in (name or "")

_STRONG_STEMS = frozenset(_STRONG_STEMS)

# Co-tokens que confirman contexto de cheat para stems ambiguos. Deliberadamente
# específicos de Minecraft: 'mods' suelto matchea Warframe/Skyrim, '.exe' matchea
# f.lux (flux.exe). Un stem ambiguo SIN ninguno de estos = se ignora.
_HACK_CO_TOKENS = (
    ".minecraft", "\\mods\\", "/mods/", ".jar", "lunarclient", "badlion",
    "\\.weave", "client", "hack", "cheat", "inject", "loader", "bypass",
    "killaura", "aimbot", "autoclick", "wallhack", "ghost", "cracked",
)

# Stems de hack que también son palabras comunes en inglés o nombres de software
# legítimo → solo cuentan como hack si hay un co-token de contexto en la ruta.
# Ejemplos de colisión: 'onyx'→nyx, 'vertex_shader.glsl'→vertex, Pandora (música),
# f.lux, VanishNoPacket (plugin MC), NVIDIA Reflex, "Extended Remix".mp3, inertia
# (física), "impact"/"future"/"rise"/"meteor"/"drip" (palabras comunes).
# NO incluir nombres de cliente distintivos (slinky, biscuit, komat, blatant,
# seppuku, zeroday, konas, vape, killaura, liquidbounce...) — deben disparar
# aunque estén camuflados / renombrados.
_AMBIGUOUS_HACK_STEMS = frozenset({
    "nyx", "kami", "lucid", "remix", "vertex", "azura", "jello", "vanish",
    "pandora", "datura", "inertia", "phobos", "wasp", "sloth", "rise", "flux",
    "sigma", "impact", "future", "meteor", "drip", "scaffold", "reflex",
    "freecam", "nofall", "xray", "fullbright", "chams",
})


def _name_indicates_hack(archivo: str, nombre: str, combo: str, patterns) -> str | None:
    """Match de nombre de hack con límites de palabra.

    Reemplaza el ``pattern in texto`` crudo. Stems ambiguos (palabras comunes /
    software legítimo) requieren un co-token de contexto (``.jar``, ``mods``,
    ``.minecraft``, ``client``, ``inject``...). Devuelve el patrón matcheado o
    ``None``.
    """
    base = os.path.basename(archivo or nombre or "").lower()
    nombre_l = (nombre or "").lower()
    combo_l = (combo or "").lower()
    has_co = any(t in combo_l for t in _HACK_CO_TOKENS)

    # 1. Match STRONG por boundary (nombres de cliente inequívocos). Solo se
    #    confía si el stem devuelto está en STRONG_STEMS: la rama ambigua de
    #    match_hack_stem ("inject", "ghost", "remix"...) se ignora acá y se
    #    re-evalúa con co-token en el paso 3.
    if _match_hack_stem is not None:
        for text in (base, nombre_l):
            hit = _match_hack_stem(text)
            if hit and hit in _STRONG_STEMS and hit not in _AMBIGUOUS_HACK_STEMS:
                return hit

    # 2. Combo Vape-inject / loader (inequívoco aunque 'vape' sea corto).
    if "vape" in combo_l and any(
        t in combo_l for t in ("inject", "loader", "dllinject", "javaagent")
    ):
        return "vape_inject"

    # 3. Patrones explícitos con boundary; ambiguos requieren co-token.
    for p in patterns:
        pl = p.lower()
        if "\\" in pl or "/" in pl:           # ruta multi-segmento: ya es específica
            if pl in combo_l:
                return p
            continue
        if not (_stem_in_filename(pl, base) or _stem_in_filename(pl, nombre_l)):
            continue
        if pl in _AMBIGUOUS_HACK_STEMS and not has_co:
            continue                          # palabra común sin contexto → ignorar
        return p
    return None


def _resolve_main_symbols():
    """Lazy bind a constantes de main (evita import circular al cargar el módulo)."""
    main_mod = sys.modules.get("main")
    if main_mod is None:
        import main as main_mod  # noqa: WPS433
    never = getattr(main_mod, "_NEVER_FILTER_TYPES", frozenset())
    definite = getattr(main_mod, "_DEFINITE_HACK_NAMES", set())
    forensic = getattr(main_mod, "_FORENSIC_PATH_EXEMPT_TYPES", frozenset())
    vanilla = getattr(main_mod, "_VANILLA_MC_PATHS", [])
    ArgusApp = getattr(main_mod, "ArgusApp", None)
    return never, definite, forensic, vanilla, ArgusApp


def normalize_path(path: str) -> str:
    """Normaliza rutas para matching FP (JSON escapado, / vs \\, casing)."""
    if not path:
        return ""
    p = str(path).replace("/", "\\").lower()
    # Colapsar backslashes dobles de JSON/reg ("c:\\users" → "c:\users")
    while "\\\\" in p:
        p = p.replace("\\\\", "\\")
    return p


def _path_segment_match(needle: str, path: str) -> bool:
    """Match más estricto que substring suelto; paths con \\ siguen siendo substring."""
    if not needle or not path:
        return False
    path = normalize_path(path)
    needle = normalize_path(needle)
    # Rutas multi-segmento: substring basta (ya son específicas)
    if "\\" in needle:
        return needle in path
    idx = 0
    n = len(needle)
    while True:
        i = path.find(needle, idx)
        if i < 0:
            return False
        before = path[i - 1] if i > 0 else "\\"
        after = path[i + n] if i + n < len(path) else "\\"
        if before in "\\/|_-. " and after in "\\/|_-. ":
            return True
        # prefijo de componente (badlionclient)
        if before in "\\/| " and (after.isalnum() or after in "-_."):
            return True
        idx = i + 1


def filter_false_positives(app, issues):
    """Filtrado MEJORADO - Detecta hacks reales pero menos estricto"""
    import psutil  # noqa: WPS433 — usado más abajo en el filtro

    (
        _NEVER_FILTER_TYPES,
        _DEFINITE_HACK_NAMES,
        _FORENSIC_PATH_EXEMPT_TYPES,
        _VANILLA_MC_PATHS,
        ArgusApp,
    ) = _resolve_main_symbols()
    if ArgusApp is None:
        ArgusApp = type(app)
    if not hasattr(ArgusApp, "_mbaz_cache"):
        ArgusApp._mbaz_cache = {}
    if not hasattr(ArgusApp, "_vt_cache"):
        ArgusApp._vt_cache = {}
    issues = app._apply_remote_fp_rules(issues)
    filtered = []
    hacks_critical = []
    hacks_sospechoso = []
    hacks_poco_sospechoso = []
    hacks_normal = []

    print(f"\n🔍 INICIANDO FILTRADO MEJORADO DE {len(issues)} ELEMENTOS...")

    # Umbral mínimo de confianza — descartar ruido < 30% (P2 #3)
    # Configurable: config.min_confidence_pct o ARGUS_MIN_CONFIDENCE
    try:
        MIN_CONFIDENCE = int(
            os.environ.get("ARGUS_MIN_CONFIDENCE")
            or (getattr(app, "config", {}) or {}).get("min_confidence_pct")
            or 30
        )
    except (TypeError, ValueError):
        MIN_CONFIDENCE = 30
    _min_exempt = set(_NEVER_FILTER_TYPES) | {
        'vpn_active', 'hosts_file_custom', 'ss_verdict', 'ss_integrity',
    }
    issues = [i for i in issues if (
        i.get('tipo', '') in _min_exempt or
        (i.get('confidence', 100) * (100 if i.get('confidence', 1) <= 1 else 1)) >= MIN_CONFIDENCE
    )]
    # NORMAL puro = ruido informativo; no llega a staff (salvo veredicto/integridad)
    _before_n = len(issues)
    issues = [
        i for i in issues
        if (i.get('alerta') or '').upper() != 'NORMAL'
        or (i.get('tipo') or '') in ('ss_verdict', 'ss_integrity')
    ]
    if len(issues) < _before_n:
        print(f"📉 Drop NORMAL: {_before_n - len(issues)} (quedan {len(issues)})")
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
        'xraymod', 'xray', 'fullbright', 'wallhack', 'boxesp', 'chams', 'traceline',
        'autoclicker', 'clickgui', 'bunnyhop', 'bhop', 'aimassist',
        'wtap', 'speedhack', 'freecam', 'nofall', 'autototem', 'autocrystal',
        # Injectors con nombre específico
        'dllinjector', 'extremeinjector',
        # Catálogo 1.8.5+
        'thunderhack', 'doomsday', 'myau', 'fdpclient', 'nightx',
        'liquidbounceplus', 'meteorrejects', 'ravenbplus',
        # Vape inject / loaders (scan #106 — no filtrar por nombre genérico)
        'vapeinject', 'vape-inject', 'vape_inject', 'vapeinjector',
        'vape-loader', 'vape_loader', 'vapeloader',
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
        # Lunar 3.x / Moonsworth (home + AppData variantes)
        '\\.lunarclient\\', 'appdata\\roaming\\.lunarclient\\',
        'appdata\\local\\.lunarclient\\', 'moonsworth\\',
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
    TRUSTED_TYPES = set(_NEVER_FILTER_TYPES)

    # Rutas donde un artefacto forense (USN/Prefetch/Amcache/BAM) es ruido, no un
    # hack — se filtra INCLUSO para tipos forense-exentos, salvo que el nombre
    # matchee un stem de hack o haya hash/YARA confirmado. Un archivo borrado del
    # cache de Chrome o un Prefetch de MSEDGE.EXE no es evidencia de cheat.
    _FORENSIC_NOISE_PATHS = (
        'google\\chrome', 'appdata\\local\\google', 'mozilla\\firefox',
        'appdata\\roaming\\mozilla', 'microsoft\\edge', 'appdata\\local\\microsoft\\edge',
        'appdata\\local\\brave-browser', 'appdata\\local\\vivaldi', 'opera software',
        'appdata\\local\\spotify', 'appdata\\roaming\\spotify', '\\spotify\\storage\\',
        'appdata\\local\\discord', 'discord\\app-',
        'windows\\system32', 'windows\\syswow64', 'windows\\softwaredistribution',
        'windows\\servicing', 'windows\\winsxs',
        'appdata\\local\\microsoft\\', 'program files\\common files\\microsoft',
        'steam\\steamapps', 'appdata\\local\\packages\\microsoft.',
    )

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
        # Sistema Windows (NO incluir Prefetch: es fuente forense primaria)
        'windows\\system32', 'windows\\syswow64',
        'windows\\winsxs', 'windows\\softwaredistribution',
        # Launchers legítimos de Minecraft (clientes oficiales)
        'lunarclient', 'lunar client', 'lunar-client',
        '.lunarclient', 'moonsworth',  # Lunar 3.x paths
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
        'appdata\\roaming\\.lunarclient\\',  # Lunar 3.x AppData
        'appdata\\local\\.lunarclient\\',
        '\\.lunarclient\\',                   # %USERPROFILE%\.lunarclient
        'moonsworth\\',
        'appdata\\local\\curseforge\\',
        'appdata\\local\\packages\\microsoft.',  # Windows Store sandboxed
    }

    # F33/F34 — Estadísticas de filtrado por motivo (para diagnóstico)
    _filter_stats = {}
    _debug_filter = os.environ.get('ARGUS_DEBUG_FILTER') == '1'
    _discarded_items = [] if _debug_filter else None  # F35: collect if debug mode
    _legit_mod_count = 0  # F25: cuenta mods legítimos verificados
    _legit_pattern_count = 0  # whitelist estática + patrones aprendidos
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
        ruta = normalize_path(item.get('ruta', '') or '')
        archivo = normalize_path(item.get('archivo', '') or '')
        tipo = item.get('tipo', '').lower()

        # ── FILTRO ABSOLUTO — software legítimo (NO aplica a forense/integridad) ──
        # Importante: NO eximir todos los TRUSTED_TYPES (usn/browser en Chrome
        # deben seguir bloqueándose). Solo tipos cuya evidencia vive en Prefetch/sistema.
        _combined_path = ruta + '|' + archivo
        _cat = (item.get('categoria') or '').upper()
        _skip_safe = (
            tipo in _FORENSIC_PATH_EXEMPT_TYPES
            or _cat == 'INTEGRITY'
            or 'windows\\prefetch' in _combined_path
        )
        # Un archivo con nombre de hack inequívoco (vape_inject.exe, killaura.dll,
        # liquidbounce.jar) NO se whitelistea por estar en una carpeta "segura":
        # es la técnica de camuflaje clásica (esconderlo en \spotify\, \discord\).
        _name_is_hack = _name_indicates_hack(
            archivo, nombre, _combined_path + '|' + nombre, real_hack_patterns
        )
        if not _skip_safe and not _name_is_hack:
            _is_absolute_safe = any(
                _path_segment_match(safe, _combined_path) for safe in ABSOLUTE_SAFE_PATHS
            )
            if _is_absolute_safe:
                _discard('SAFE_PATH', nombre, ruta)
                continue

        # ── Ruido forense de navegadores / apps legítimas ─────────────────────
        # Aplica aun a tipos forense-exentos (usn/prefetch/amcache/bam) salvo que
        # el nombre matchee un stem de hack o haya hash/YARA confirmado.
        if _skip_safe and _cat != 'INTEGRITY' and 'windows\\prefetch' not in _combined_path:
            _pats_now = ' '.join(str(p) for p in (item.get('detected_patterns') or [])).lower()
            _has_hack_evidence = (
                'cloud_hash' in _pats_now or 'malwarebazaar' in _pats_now
                or 'vt_' in _pats_now or 'yara' in _pats_now
                or _name_indicates_hack(
                    archivo, nombre, _combined_path + '|' + nombre, real_hack_patterns
                ) is not None
            )
            if not _has_hack_evidence and any(
                _path_segment_match(safe, _combined_path) for safe in _FORENSIC_NOISE_PATHS
            ):
                _discard('FORENSIC_APP_NOISE', nombre, ruta)
                continue

        # P1 #162 — Whitelist por categoría de software legítimo
        _CAT_KEEP = {
            'recycle_hash_match', 'yara_java', 'injected_thread',
            'ghost_client_config', 'amcache_hack_execution', 'prefetch_hack',
            'prefetch_referenced_hack', 'ss_integrity', 'ss_verdict',
        }
        if tipo not in TRUSTED_TYPES and tipo not in _CAT_KEEP and not _skip_safe:
            _blob_cat = _combined_path + '|' + nombre
            _cat_hit = None
            if any(f in _blob_cat for f in (
                'prismlauncher', 'multimc', 'lunarclient', '.lunarclient',
                'badlion', 'tlauncher', 'atlauncher', 'gdlauncher', 'curseforge',
                'modrinth app', 'ftb app', 'overwolf',
            )):
                _cat_hit = 'launcher'
            elif any(f in _blob_cat for f in (
                'fabric-loader', 'fabricloader', 'minecraftforge', 'neoforge',
                'quilt-loader',
            )):
                _cat_hit = 'mod_loader'
            elif any(f in _blob_cat for f in (
                'sodium-', 'lithium-', 'starlight-', 'phosphor-', 'iris-',
                'ferritecore-', 'entityculling-', 'lazydfu-',
            )):
                _cat_hit = 'perf_mod'
            elif any(f in _blob_cat for f in (
                'jei-', 'rei-', 'emi-', 'xaero', 'journeymap', 'voxelmap',
            )):
                _cat_hit = 'qol_mod'
            if _cat_hit:
                _discard(f'CAT_WL_{_cat_hit}', nombre, ruta)
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
        _item_path_lower = normalize_path(item.get('ruta') or item.get('archivo') or '')
        _in_active_instance = False
        try:
            _active_paths = app._get_active_launcher_instance_paths()
            if _active_paths and any(_item_path_lower.startswith(ap) for ap in _active_paths):
                _in_active_instance = True
        except Exception:
            pass

        # F6 — Instancias antiguas/abandonadas (>60 días sin lanzar) → bajar severidad
        # No aplicar si la instancia está marcada como activa en profiles.json (F9)
        if not _in_active_instance:
            try:
                _abandoned_paths = app._get_abandoned_instance_paths()
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
                if app._is_legitimate_mod_jar(str(_jar_path)):
                    print(f"✅ [ManifestCheck] Mod legítimo (fabric/forge/quilt): {os.path.basename(str(_jar_path))}")
                    _legit_mod_count += 1
                    continue
                if app._is_modrinth_legitimate(str(_jar_path)):
                    print(f"✅ [Modrinth] Mod legítimo verificado: {os.path.basename(str(_jar_path))}")
                    _legit_mod_count += 1
                    continue
                if app._is_curseforge_legitimate(str(_jar_path)):
                    print(f"✅ [CurseForge] Mod legítimo verificado: {os.path.basename(str(_jar_path))}")
                    _legit_mod_count += 1
                    continue
                # Fast-path: patrones legítimos (mods MC / rutas conocidas) antes de VT
                if app.legitimate_patterns:
                    try:
                        _jar_name_lp = os.path.basename(str(_jar_path)).lower()
                        try:
                            from config.hack_signatures import filename_is_definite_hack as _is_hack_jar
                        except ImportError:
                            def _is_hack_jar(_n):  # type: ignore
                                return False
                        if not _is_hack_jar(_jar_name_lp):
                            _lp_ok, _lp_conf = app.legitimate_patterns.is_legitimate(
                                file_path=str(_jar_path),
                                file_name=_jar_name_lp,
                                file_hash=item.get('file_hash'),
                                context={'file_path': str(_jar_path)},
                            )
                            if _lp_ok and _lp_conf >= 0.5:
                                print(
                                    f"✅ [LegitPattern] Mod/ruta legítima: "
                                    f"{os.path.basename(str(_jar_path))} (conf={_lp_conf:.2f})"
                                )
                                _legit_mod_count += 1
                                _legit_pattern_count += 1
                                continue
                    except Exception:
                        pass

        # P2 #1+8 — VirusTotal + MalwareBazaar para .exe/.jar sospechosos
        _vt_path = item.get('archivo') or item.get('ruta') or ''
        _alerta  = item.get('alerta', 'NORMAL')
        if (_alerta in ('SOSPECHOSO', 'CRITICAL') and _vt_path and
                os.path.isfile(str(_vt_path)) and
                any(str(_vt_path).lower().endswith(e) for e in ('.exe', '.jar', '.dll'))):
            try:
                _sha256_vt = app._cached_sha256(str(_vt_path))
                if not _sha256_vt:
                    continue
                # MalwareBazaar (gratis, sin API key)
                if _sha256_vt not in ArgusApp._mbaz_cache:
                    ArgusApp._mbaz_cache[_sha256_vt] = app._mbaz_check_hash(_sha256_vt)
                if ArgusApp._mbaz_cache.get(_sha256_vt):
                    print(f"🚨 [MalwareBazaar] Hash en BD de malware: {os.path.basename(str(_vt_path))}")
                    item['alerta'] = 'CRITICAL'
                    item['confidence'] = min(0.99, float(item.get('confidence', 0.5)) + 0.35)
                    item['detected_patterns'] = list(item.get('detected_patterns', [])) + ['malwarebazaar']
                # VirusTotal (requiere VIRUSTOTAL_API_KEY)
                if _sha256_vt not in ArgusApp._vt_cache:
                    ArgusApp._vt_cache[_sha256_vt] = app._vt_check_hash(_sha256_vt)
                _vt_result = ArgusApp._vt_cache.get(_sha256_vt)
                if _vt_result is not None:
                    _pos, _tot = _vt_result
                    if _pos == 0 and _tot > 10:
                        # No degradar si hay firma fuerte / hash cloud / forense
                        _bn = os.path.basename(str(_vt_path)).lower()
                        _strong = False
                        try:
                            from config.hack_signatures import filename_is_definite_hack
                            _strong = filename_is_definite_hack(_bn)
                        except Exception:
                            pass
                        _pats = set(item.get('detected_patterns') or [])
                        if (
                            _strong
                            or tipo in _FORENSIC_PATH_EXEMPT_TYPES
                            or tipo in ('cloud_hash_match', 'prefetch_hack', 'yara_java')
                            or any(x.startswith('malwarebazaar') or x.startswith('vt_') for x in _pats)
                            or 'cloud_hash' in _pats
                        ):
                            item['detected_patterns'] = list(_pats) + ['vt_clean_ignored']
                        else:
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
                _sha256_f23 = app._cached_sha256(str(_f23_path), max_bytes=8 * 1024 * 1024)
                if not _sha256_f23:
                    raise OSError('hash failed')
                _freq = app._cloud_hash_frequency.get(_sha256_f23.lower(), 0)
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

        # Camuflaje: un archivo con nombre de hack inequívoco no se whitelistea
        # por ruta/patrón legítimo (esconderlo en \spotify\, \adobe\, \shaders\...).
        _skip_fp_whitelist = _name_is_hack is not None

        # Verificar con sistema de patrones legítimos aprendidos
        if app.legitimate_patterns and not _skip_fp_whitelist:
            try:
                file_hash = item.get('file_hash', '')
                is_legitimate, legit_confidence = app.legitimate_patterns.is_legitimate(
                    file_path=ruta or archivo,
                    file_name=archivo or nombre,
                    file_hash=file_hash,
                    context={'file_path': ruta or archivo}
                )

                if is_legitimate and legit_confidence >= 0.5:
                    is_false_positive = True
                    _legit_pattern_count += 1
                    print(f"✅ Filtrado como legítimo aprendido: {archivo or nombre} (confianza: {legit_confidence:.2f})")
            except Exception as e:
                pass

        # Verificar patrones de exclusión (segment-aware para stems cortos)
        if not is_false_positive and not _skip_fp_whitelist:
            _ex_blob = f"{ruta}|{archivo}|{nombre}"
            for pattern in exclude_patterns:
                if _path_segment_match(pattern, _ex_blob) or (
                    ("\\" in pattern or "/" in pattern) and pattern in _ex_blob
                ):
                    is_false_positive = True
                    break

        # Verificar falsos positivos específicos adicionales
        if not is_false_positive and not _skip_fp_whitelist:
            _fp_blob = f"{ruta}|{archivo}|{nombre}"
            for false_positive in ['zomboid', 'shaders\\', '\\textures\\', 'system32', '\\program files\\', '\\windows\\system', 'microsoft\\', 'adobe\\']:
                if _path_segment_match(false_positive, _fp_blob) or false_positive in _fp_blob:
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
                    elif _age_days > 180:
                        # P1 #164 — >180d sin actividad reciente: soft demote fuerte
                        if item.get('alerta') == 'CRITICAL':
                            item['alerta'] = 'SOSPECHOSO'
                        elif item.get('alerta') == 'SOSPECHOSO':
                            item['alerta'] = 'POCO_SOSPECHOSO'
                        item['confidence'] = max(0.18, float(item.get('confidence', 0.5)) * 0.65)
                        item.setdefault('detected_patterns', []).append(f'file_age_{int(_age_days)}d_wl')
                    elif _age_days > 90:
                        # F22: Entre 90 y 180 días — reducción moderada
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
                    content_analysis = app.analyze_file_content(str(file_path))
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

        # 3. ACEPTAR SI CONTIENE PATRONES DE HACKS (nombre, archivo o ruta completa)
        # Match con límites de palabra: 'onyx' ya no dispara 'nyx', 'three_vertex'
        # ya no dispara 'vertex'. Stems ambiguos exigen un co-token de contexto.
        # _name_indicates_hack ya cubre combined_path_indicates_hack (boundary +
        # combo vape-inject) sin el falso positivo de filename_is_definite_hack
        # sobre palabras comunes ("Extended Remix.mp3", "vertex_shader.glsl").
        _hack_match = _name_is_hack  # ya calculado antes del filtro SAFE_PATH
        is_potential_hack = _hack_match is not None

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
            matched_definite = _hack_match
            if matched_definite and (matched_definite in _DEFINITE_HACK_NAMES
                                     or matched_definite == "definite_hack"):
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
        'ghost_client_config', 'ghost_client_registry', 'blacklisted_mod',
        'modified_minecraft_jar', 'weave_loader', 'recycle_hack',
    }
    FORENSIC_TYPES = {
        'prefetch_hack', 'bam_suspicious', 'usn_deleted_hack', 'usn_ghost_folder',
        'amcache_hack_execution', 'userassist_suspicious', 'shimcache_suspicious',
    }
    for group in (JAVA_INJECTION_TYPES, AUTOCLICK_TYPES, GHOST_TYPES, FORENSIC_TYPES):
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
    if _legit_mod_count:
        print(f"✅ MODS/RUTAS LEGÍTIMAS (manifest/modrinth/patrones): {_legit_mod_count}")
    if _legit_pattern_count:
        print(f"✅ FILTRADOS POR LegitPattern: {_legit_pattern_count}")
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
    filtered = app._filter_by_file_size(filtered)

    # P2 #28 — Reducir score de archivos en rutas de sync cloud
    filtered = app._filter_backup_sync(filtered)

    # P2 #22 — Decay de score por antigüedad de evidencia
    filtered = app._apply_score_decay(filtered)

    # P2 #30 — Umbrales dinámicos ajustados por feedback loop
    filtered = app._apply_feedback_thresholds(filtered)

    # P2 #23 — Agregar explicaciones en español a todos los hallazgos
    filtered = app._apply_human_explanations(filtered)

    # Dedupe exacto (mismo tipo + ruta + nombre)
    try:
        from scanner_dedupe import dedupe_issues
        filtered = dedupe_issues(filtered)
    except ImportError:
        pass

    # P2 #24 — Agrupar resultados repetidos del mismo tipo
    filtered = app._group_related_results(filtered)

    # P2 #13 — Descarta procesos conocidos y seguros
    filtered = app._apply_process_whitelist(filtered)

    # P2 #14 — Nombre genérico + ruta (Program Files vs TEMP)
    try:
        filtered = app._apply_process_path_correlation(filtered)
    except Exception:
        pass

    # P2 #6 — Parent launcher legítimo
    try:
        filtered = app._apply_legit_parent_demote(filtered)
    except Exception:
        pass

    # P2 #7 — Authenticode trusted publisher / signed Program Files
    try:
        filtered = app._apply_authenticode_demote(filtered)
    except Exception:
        pass

    # P2 #15 — uptime largo → demote; P2 #27 Badlion/Lunar informativo
    try:
        filtered = app._apply_long_uptime_demote(filtered)
    except Exception:
        pass
    try:
        filtered = app._apply_badlion_informational(filtered)
    except Exception:
        pass

    # P3 #2 + #16 — Ajuste dinámico de confidence por rareza y patrones de bans
    filtered = app._apply_cloud_rarity_and_ban_patterns(filtered)

    # P2 #5 — Archivos viejos sin evidencia de ejecución
    try:
        filtered = app._apply_stale_artifact_demote(filtered)
    except Exception:
        pass

    # P2 #4 — Indicador aislado: cap a SOSPECHOSO si no hay 2+ evidencias independientes
    filtered = app._apply_single_indicator_cap(filtered)

    # P2 #21 — Escalar a CRITICAL por combinaciones de evidencias
    filtered = app._apply_combination_penalties(filtered)

    # v1.5 — Boost/desescalar por contexto global del scan
    filtered = app._ai_contextual_boost(filtered)

    # Métricas staff: motivos de descarte por scan
    try:
        app.last_filter_stats = dict(_filter_stats)
        app.last_filter_stats['_kept'] = len(filtered)
        app.last_filter_stats['_input'] = len(issues)
        _dump_filter_stats(app.last_filter_stats)
    except Exception:
        pass

    print(f"📋 TOTAL FINAL (tras decay + agrupación): {len(filtered)}")
    return filtered


def _dump_filter_stats(stats: dict) -> None:
    """Escribe perf/filter_stats.json junto al scanner (o cwd)."""
    try:
        import json
        from datetime import datetime, timezone
        base = os.environ.get("LOCALAPPDATA") or os.getcwd()
        d = os.path.join(base, "ArgusScanner", "perf")
        os.makedirs(d, exist_ok=True)
        payload = {
            "ts": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
            "stats": stats,
        }
        path = os.path.join(d, "filter_stats.json")
        with open(path, "w", encoding="utf-8") as f:
            json.dump(payload, f, ensure_ascii=False, indent=2)
        # también línea compacta en log
        top = sorted(
            ((k, v) for k, v in stats.items() if not str(k).startswith("_")),
            key=lambda x: -int(x[1] or 0),
        )[:6]
        _safe_print("[filter_stats] " + ", ".join(f"{k}={v}" for k, v in top))
    except Exception:
        pass


def _safe_print(msg: str) -> None:
    try:
        print(msg)
    except UnicodeEncodeError:
        try:
            print(msg.encode("ascii", "replace").decode("ascii"))
        except Exception:
            pass


def secondary_filter(app, issues):
    """Segundo filtro más inteligente — menos escalado agresivo a CRITICAL (v1.8+)."""
    try:
        _safe_print("[filter] APLICANDO SEGUNDO FILTRO INTELIGENTE...")
        (
            _NEVER_FILTER_TYPES,
            _DEFINITE_HACK_NAMES,
            _FORENSIC_PATH_EXEMPT_TYPES,
            _VANILLA_MC_PATHS,
            _Argus,
        ) = _resolve_main_symbols()
        try:
            from config.hack_signatures import filename_is_definite_hack, stem_in_filename
        except Exception:
            def filename_is_definite_hack(_f):  # type: ignore
                return False
            def stem_in_filename(stem, name):  # type: ignore
                return stem in (name or '')

        real_hack_patterns = [
            'fluxclient', 'flux 1.8', 'flux1.8', 'vapelite', 'vape v4', 'vapev4',
            'entropyclient', 'whiteoutclient', 'liquidbounce', 'wurstclient',
            'impactclient', 'sigmaclient', 'futureclient', 'astolfoclient',
            'exhibitionclient', 'novolineclient', 'riseclient', 'moonclient',
            'dripclient', 'ghostclient', 'meteorclient', 'rusherhack',
            'thunderhack', 'doomsday', 'myau', 'fdpclient', 'nightx',
            'weaveloader', 'liquidbounceplus', 'ravenbplus',
        ]
        # Keywords fuertes (no 'hack'/'cheat'/'inject' solos)
        strong_keywords = (
            'killaura', 'aimbot', 'wallhack', 'triggerbot', 'vapeinject',
            'selfdestruct', 'ghostclient',
        )

        filtered_issues = []

        for issue in issues:
            nombre = issue.get('nombre', '').lower()
            ruta = issue.get('ruta', '').lower()
            archivo = issue.get('archivo', '').lower()
            tipo = issue.get('tipo', '')
            cat = (issue.get('categoria') or '').upper()
            base = os.path.basename(archivo or ruta)

            if tipo in _NEVER_FILTER_TYPES or tipo in _FORENSIC_PATH_EXEMPT_TYPES or cat == 'INTEGRITY':
                filtered_issues.append(issue)
                continue

            is_real_hack = False
            definite = filename_is_definite_hack(base) or filename_is_definite_hack(nombre)

            if definite:
                is_real_hack = True
            else:
                for pattern in real_hack_patterns:
                    if pattern in nombre or pattern in ruta or pattern in archivo:
                        is_real_hack = True
                        break
                if not is_real_hack:
                    for kw in strong_keywords:
                        if stem_in_filename(kw, nombre) or stem_in_filename(kw, base):
                            is_real_hack = True
                            break
                if not is_real_hack and tipo in ('hack_file', 'exact_hack_folder'):
                    is_real_hack = True
                # Downloads/Desktop + jar/exe → solo SOSPECHOSO si no es definite
                _out = any(loc in ruta for loc in ('downloads', 'desktop', 'documents'))
                _ext = base.endswith(('.jar', '.exe'))
                if not is_real_hack and _out and _ext:
                    issue['alerta'] = 'SOSPECHOSO'
                    try:
                        issue['confidence'] = min(float(issue.get('confidence', 0.55)), 0.55)
                    except Exception:
                        issue['confidence'] = 0.55
                    if not issue.get('categoria'):
                        issue['categoria'] = 'HACKS'
                    issue['detected_patterns'] = list(issue.get('detected_patterns') or []) + [
                        'secondary:downloads_soft'
                    ]
                    filtered_issues.append(issue)
                    continue

            if is_real_hack:
                _in_instance = any(
                    f in ruta for f in (
                        '.minecraft', 'minecraft\\mods', 'lunarclient',
                        'badlion', 'prismlauncher', 'multimc',
                    )
                )
                _out_of_inst = any(
                    loc in ruta for loc in (
                        'downloads', 'desktop', 'documents', '\\temp\\', '/temp/',
                    )
                )
                if definite and _in_instance:
                    issue['alerta'] = 'CRITICAL'
                elif _out_of_inst and not _in_instance:
                    issue['alerta'] = 'SOSPECHOSO'
                    issue['confidence'] = min(float(issue.get('confidence', 0.7) or 0.7), 0.65)
                elif definite:
                    issue['alerta'] = 'CRITICAL'
                else:
                    # Nombre ambiguo: no forzar CRITICAL
                    if issue.get('alerta') not in ('CRITICAL', 'SOSPECHOSO'):
                        issue['alerta'] = 'SOSPECHOSO'
                if not issue.get('categoria'):
                    issue['categoria'] = 'HACKS'
                filtered_issues.append(issue)
                _safe_print(f"[filter] HACK REAL DETECTADO: {nombre} en {ruta}")
            else:
                if issue.get('alerta') in ('SOSPECHOSO', 'POCO_SOSPECHOSO', 'CRITICAL') or issue.get('categoria'):
                    filtered_issues.append(issue)

        _safe_print(f"[filter] SEGUNDO FILTRO APLICADO: {len(filtered_issues)} elementos clasificados")
        return filtered_issues

    except Exception as e:
        _safe_print(f"Error aplicando segundo filtro: {e}")
        return issues

