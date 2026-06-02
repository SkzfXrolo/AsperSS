"""Prepara source/bundle/ — solo contenido útil (sin relleno al build)."""
from __future__ import annotations

import hashlib
import json
import os
import re
import shutil
import sqlite3
import struct
import sys
import zipfile

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
BUNDLE = os.path.join(ROOT, 'bundle')
API_DEFAULT = 'https://asperss.onrender.com'

_FILENAME_SUFFIXES = (
    '', '.jar', '.exe', '.dll', '.zip', '.rar', '.7z',
    '-1.8.9.jar', '-1.7.10.jar', '-1.20.jar', '-1.20.1.jar',
    '_v4.jar', '_v2.jar', '.disabled', '.bak', '.old',
    '_client.jar', '-client.jar', '.litemod', '.input',
)


def _copy_scanner_db():
    candidates = [
        os.path.join(ROOT, 'dist_new3', 'scanner_db.sqlite'),
        os.path.join(ROOT, 'dist_new', 'scanner_db.sqlite'),
        os.path.join(ROOT, 'scanner_db.sqlite'),
    ]
    dst = os.path.join(BUNDLE, 'scanner_db.sqlite')
    for src in candidates:
        if os.path.isfile(src) and os.path.getsize(src) > 100_000:
            shutil.copy2(src, dst)
            print(f'[bundle] scanner_db.sqlite <- {src} ({os.path.getsize(dst) // 1024} KB)')
            return
    print('[bundle] WARN: no scanner_db.sqlite grande encontrado')


def _collect_hack_stems() -> set[str]:
    stems: set[str] = set()
    try:
        sys.path.insert(0, ROOT)
        from config.hack_signatures import (
            NEVER_LEGITIMATE_STEMS,
            BLACKLISTED_MOD_STEMS,
            VAPE_INJECT_STEMS,
            BOUNDARY_ONLY_MOD_STEMS,
        )
        for s in NEVER_LEGITIMATE_STEMS:
            stems.add(str(s).lower())
        for s in BLACKLISTED_MOD_STEMS:
            stems.add(str(s).lower())
        for s in VAPE_INJECT_STEMS:
            stems.add(str(s).lower())
        for s in BOUNDARY_ONLY_MOD_STEMS:
            stems.add(str(s).lower())
    except Exception as e:
        print(f'[bundle] hack_signatures: {e}')

    main_py = os.path.join(ROOT, 'main.py')
    if os.path.isfile(main_py):
        try:
            text = open(main_py, 'r', encoding='utf-8', errors='replace').read()
            block = text
            if 'hacks_keywords' in text:
                start = text.find('hacks_keywords')
                block = text[start:start + 12000] if start >= 0 else text
            for m in re.findall(r"'([a-zA-Z0-9][a-zA-Z0-9._\-]{2,48})'", block):
                low = m.lower()
                if any(k in low for k in (
                    'vape', 'inject', 'hack', 'click', 'aura', 'client', 'cheat',
                    'xray', 'baritone', 'wurst', 'entropy', 'meteor', 'sigma',
                )):
                    stems.add(low)
        except Exception:
            pass

    extra = (
        'autoclicker', 'jitterclick', 'ghostclient', 'liquidbounce', 'wurstclient',
        'impactclient', 'fluxclient', 'futureclient', 'astolfo', 'novoline',
        'rusherhack', 'dripclient', 'thunderhack', 'weepcraft', 'konas',
        'pyautogui', 'autohotkey', 'tinytools', 'weightclick', 'clickbot',
        'pvpinjector', 'dllinjector', 'cheatengine', 'processhacker',
    )
    stems.update(extra)
    return stems


def _write_offline_lexicon(stems: set[str]):
    try:
        sys.path.insert(0, ROOT)
        from config.hack_signatures import (
            NEVER_LEGITIMATE_STEMS,
            BLACKLISTED_MOD_STEMS,
            VAPE_INJECT_STEMS,
            BOUNDARY_ONLY_MOD_STEMS,
        )
        payload = {
            'version': 2,
            'stem_count': len(stems),
            'never_legitimate': sorted(NEVER_LEGITIMATE_STEMS),
            'blacklisted_mods': list(BLACKLISTED_MOD_STEMS),
            'vape_inject': list(VAPE_INJECT_STEMS),
            'boundary_only': list(BOUNDARY_ONLY_MOD_STEMS),
            'expanded_stems': sorted(stems)[:8000],
        }
    except Exception as e:
        payload = {'version': 2, 'error': str(e), 'expanded_stems': sorted(stems)}

    path = os.path.join(BUNDLE, 'offline_lexicon.json')
    with open(path, 'w', encoding='utf-8') as f:
        json.dump(payload, f, ensure_ascii=False, separators=(',', ':'))
    print(f'[bundle] offline_lexicon.json ({os.path.getsize(path) // 1024} KB, {len(stems)} stems)')


def _write_scan_profile():
    """Rutas y reglas de escaneo embebidas (arranque sin importar todo main)."""
    try:
        sys.path.insert(0, ROOT)
        from config import scan_paths
        payload = {
            'version': 1,
            'relevant_extensions': sorted(scan_paths.RELEVANT_EXTENSIONS),
            'skip_dir_names': sorted(scan_paths.SKIP_DIR_NAMES),
            'skip_path_fragments': list(scan_paths.SKIP_PATH_FRAGMENTS),
            'mc_vanilla_dirs': sorted(scan_paths.MC_VANILLA_DIR_NAMES),
            'depth_default': scan_paths.DEPTH_DEFAULT,
            'depth_mc_root': scan_paths.DEPTH_MC_ROOT,
        }
    except Exception as e:
        payload = {'version': 1, 'error': str(e)}

    path = os.path.join(BUNDLE, 'offline_scan_profile.json')
    with open(path, 'w', encoding='utf-8') as f:
        json.dump(payload, f, ensure_ascii=False, indent=2)
    print(f'[bundle] offline_scan_profile.json ({os.path.getsize(path) // 1024} KB)')


def _write_staff_guide():
    html = """<!DOCTYPE html><html lang="es"><head><meta charset="utf-8">
<title>Argus Scanner 1.7 — Guía staff (offline)</title>
<style>body{font-family:Segoe UI,sans-serif;background:#09090b;color:#e4e4e7;max-width:760px;margin:2rem auto;padding:0 1rem}
h1{color:#E8A86F}h2{color:#B87333;margin-top:1.4rem}code,kbd{background:#1f1f23;padding:2px 6px;border-radius:4px}
ul{line-height:1.65} li{margin:.35rem 0}</style></head><body>
<h1>Argus Scanner v1.7.0</h1>
<p>Guía embebida en el .exe. Esta build incluye pack forense ampliado y arranque sin congelar al validar token.</p>
<h2>Novedades v1.7</h2>
<ul>
<li><strong>89 módulos</strong> — 28 scanners pkg, 28 SSForensics, 30 superficies nuevas (launchers/remote), 3 minado.</li>
<li><strong>Offline</strong> — SQLite, catálogo SHA256, lexicon, perfil de rutas; funciona sin red al inicio.</li>
<li><strong>Token sin lag</strong> — verificación en segundo plano; luego “Preparando motor…”.</li>
<li><strong>Beta</strong> — <kbd>Ctrl+Shift+M</kbd> para activar/desactivar cada módulo.</li>
</ul>
<h2>Antes del SS</h2>
<ul>
<li><strong>Licencia SS</strong> (<code>argus_lic_</code>): el .exe se autentica solo; no hace falta código.</li>
<li>Fallback: token de 6 caracteres del panel.</li>
<li>Revisar alertas <strong>Mouse</strong> (peso, click-bug, reconexiones históricas).</li>
</ul>
<h2>Durante el escaneo</h2>
<ul>
<li>No cerrar la ventana hasta que staff confirme subida al panel.</li>
<li>Filtros de empresa y FP de IA se cargan en background si hay API.</li>
<li>Fase “Pack v1.7” — módulos en paralelo (timeout configurable en Beta).</li>
</ul>
<h2>Mouse / prison</h2>
<ul>
<li>En vivo: botón sostenido, patrón mecánico, USB durante SS.</li>
<li>Pasado: <code>MOUSE_WEIGHT_PAST_USAGE</code> agrupa setupapi, Event Log, Prefetch, BAM.</li>
<li>Windows no registra “peso en el botón”; se infiere por rastros de la técnica.</li>
</ul>
<h2>Después</h2>
<ul>
<li>Resultados en el panel Argus; sección mouse y forensics separadas.</li>
<li>Resumen Discord opcional al portapapeles tras el upload.</li>
</ul>
<p style="color:#71717a;font-size:0.85rem">Argus Projects — embebido en ArgusScanner.exe v1.7</p>
</body></html>"""
    path = os.path.join(BUNDLE, 'docs', 'staff_guide_offline.html')
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, 'w', encoding='utf-8') as f:
        f.write(html)
    print(f'[bundle] docs/staff_guide_offline.html ({os.path.getsize(path) // 1024} KB)')


def _generate_ui_assets():
    """Texturas splash embebidas (PNG reales, no relleno)."""
    try:
        from PIL import Image, ImageDraw
    except ImportError:
        print('[bundle] PIL no disponible — omitiendo ui_assets')
        return

    assets_dir = os.path.join(BUNDLE, 'ui_assets')
    os.makedirs(assets_dir, exist_ok=True)

    specs = (
        ('splash_ultra.png', (5120, 2880)),
        ('splash_4k.png', (3840, 2160)),
        ('splash_1920.png', (1920, 1080)),
        ('splash_1280.png', (1280, 720)),
        ('panel_banner.png', (1280, 400)),
        ('wordmark_tile.png', (512, 512)),
    )
    for fname, (w, h) in specs:
        img = Image.new('RGB', (w, h))
        px = img.load()
        for y in range(h):
            t = y / max(h - 1, 1)
            r = int(9 + 28 * t)
            g = int(9 + 18 * t)
            b = int(11 + 8 * (1 - t))
            for x in range(w):
                n = (hash((x, y)) & 7) - 3
                px[x, y] = (
                    max(0, min(255, r + n)),
                    max(0, min(255, g + n)),
                    max(0, min(255, b + n)),
                )
        draw = ImageDraw.Draw(img)
        title = 'ARGUS PROJECTS'
        tw, th = draw.textbbox((0, 0), title)[2:4]
        draw.text(((w - tw) // 2, (h - th) // 2 - 20), title, fill=(232, 168, 111))
        draw.text(((w - 180) // 2, (h + th) // 2 + 10), 'Security Scanner', fill=(161, 161, 170))
        out = os.path.join(assets_dir, fname)
        img.save(out, format='PNG', optimize=False, compress_level=1)
        print(f'[bundle] ui_assets/{fname} ({os.path.getsize(out) // 1024} KB)')


def _copy_config_defaults():
    cfg_dst = os.path.join(BUNDLE, 'config')
    os.makedirs(cfg_dst, exist_ok=True)
    for name in ('scanner_custom.json',):
        src = os.path.join(ROOT, 'config', name)
        if os.path.isfile(src):
            shutil.copy2(src, os.path.join(cfg_dst, name))
            print(f'[bundle] config/{name}')


def _export_sqlite_payload():
    db = os.path.join(BUNDLE, 'scanner_db.sqlite')
    if not os.path.isfile(db):
        return
    out = os.path.join(BUNDLE, 'offline_db_export.json')
    payload = {'version': 1, 'tables': {}}
    try:
        conn = sqlite3.connect(db)
        cur = conn.cursor()
        cur.execute("SELECT name FROM sqlite_master WHERE type='table'")
        for (tname,) in cur.fetchall():
            if tname.startswith('sqlite_'):
                continue
            try:
                cur.execute(f'SELECT * FROM "{tname}"')
                cols = [d[0] for d in cur.description]
                rows = [dict(zip(cols, row)) for row in cur.fetchall()]
                if rows:
                    payload['tables'][tname] = rows
            except Exception:
                continue
        conn.close()
        with open(out, 'w', encoding='utf-8') as f:
            json.dump(payload, f, ensure_ascii=False, separators=(',', ':'))
        print(f'[bundle] offline_db_export.json ({os.path.getsize(out) // 1024} KB)')
    except Exception as e:
        print(f'[bundle] export sqlite skip: {e}')


def _sqlite_hex_hashes() -> set[bytes]:
    found: set[bytes] = set()
    hex64 = re.compile(r'^[a-fA-F0-9]{64}$')
    db = os.path.join(BUNDLE, 'scanner_db.sqlite')
    if not os.path.isfile(db):
        return found
    try:
        conn = sqlite3.connect(db)
        cur = conn.cursor()
        cur.execute("SELECT name FROM sqlite_master WHERE type='table'")
        for (tname,) in cur.fetchall():
            try:
                cur.execute(f'SELECT * FROM "{tname}"')
                for row in cur.fetchall():
                    for cell in row:
                        if isinstance(cell, str) and hex64.match(cell.strip()):
                            found.add(bytes.fromhex(cell.strip().lower()))
            except Exception:
                continue
        conn.close()
    except Exception:
        pass
    return found


def _build_hash_catalog(stems: set[str]):
    """Catálogo denso SHA256 (archivo + variantes de nombre) — lookup offline real."""
    catalog: set[bytes] = set()
    catalog |= _sqlite_hex_hashes()

    export_path = os.path.join(BUNDLE, 'offline_db_export.json')
    if os.path.isfile(export_path):
        hex64 = re.compile(r'[a-fA-F0-9]{64}')
        with open(export_path, 'r', encoding='utf-8') as f:
            for m in hex64.findall(f.read()):
                try:
                    catalog.add(bytes.fromhex(m.lower()))
                except ValueError:
                    pass

    for stem in stems:
        if not stem:
            continue
        for suf in _FILENAME_SUFFIXES:
            for variant in (stem + suf, stem.replace('-', '_') + suf, stem.replace('_', '-') + suf):
                catalog.add(hashlib.sha256(variant.lower().encode('utf-8')).digest())

    path = os.path.join(BUNDLE, 'offline_hash_catalog.bin')
    ordered = sorted(catalog)
    with open(path, 'wb') as f:
        f.write(struct.pack('<4sII', b'AHC2', 2, len(ordered)))
        for digest in ordered:
            f.write(digest)
    print(f'[bundle] offline_hash_catalog.bin ({os.path.getsize(path) // 1024} KB, {len(ordered)} entradas)')


def _fetch_cloud_payloads():
    try:
        import requests
    except ImportError:
        print('[bundle] requests no instalado — omitiendo fetch API')
        return

    api = os.environ.get('ARGUS_API_URL', API_DEFAULT).rstrip('/')
    endpoints = (
        ('hack_hashes_cloud.json', '/api/hashes'),
        ('ai_model_offline.json', '/api/ai-model/latest'),
    )
    for fname, ep in endpoints:
        try:
            r = requests.get(f'{api}{ep}', timeout=45)
            if r.status_code == 200:
                out = os.path.join(BUNDLE, fname)
                with open(out, 'wb') as f:
                    f.write(r.content)
                print(f'[bundle] {fname} ({os.path.getsize(out) // 1024} KB) desde API')
        except Exception as e:
            print(f'[bundle] fetch {ep}: {e}')

    for src_name, dst_name in (
        ('dist_new3/models/ai_model_latest.json', 'ai_model_offline.json'),
        ('dist_new2/models/ai_model_latest.json', 'ai_model_offline.json'),
    ):
        src = os.path.join(ROOT, src_name)
        dst = os.path.join(BUNDLE, dst_name)
        if os.path.isfile(src) and (not os.path.isfile(dst) or os.path.getsize(src) > os.path.getsize(dst)):
            shutil.copy2(src, dst)


def _copy_offline_hash_cache():
    appdata = os.path.join(os.environ.get('APPDATA', ''), 'ASPERSProjectsSS', 'hack_hashes.json')
    if os.path.isfile(appdata) and os.path.getsize(appdata) > 5000:
        shutil.copy2(appdata, os.path.join(BUNDLE, 'hack_hashes_offline.json'))
        print(f'[bundle] hack_hashes_offline.json ({os.path.getsize(appdata) // 1024} KB)')


def _zip_scanner_sources():
    out = os.path.join(BUNDLE, 'scanner_modules_reference.zip')
    include = ('scanners', 'scan_modules', 'ss_forensics.py', 'mouse_weight_detector.py', 'bundle_runtime.py')
    with zipfile.ZipFile(out, 'w', zipfile.ZIP_DEFLATED, compresslevel=6) as zf:
        for item in include:
            path = os.path.join(ROOT, item)
            if os.path.isfile(path):
                zf.write(path, os.path.basename(path))
            elif os.path.isdir(path):
                for dp, _, files in os.walk(path):
                    for fn in files:
                        if fn.endswith(('.py', '.json')):
                            full = os.path.join(dp, fn)
                            zf.write(full, os.path.relpath(full, ROOT))
    print(f'[bundle] scanner_modules_reference.zip ({os.path.getsize(out) // 1024} KB)')


def main():
    os.makedirs(BUNDLE, exist_ok=True)
    stems = _collect_hack_stems()
    _copy_scanner_db()
    _write_offline_lexicon(stems)
    _write_scan_profile()
    _write_staff_guide()
    _generate_ui_assets()
    _copy_config_defaults()
    _export_sqlite_payload()
    _build_hash_catalog(stems)
    _fetch_cloud_payloads()
    _zip_scanner_sources()
    _copy_offline_hash_cache()

    # Quitar artefactos viejos con relleno falso
    for obsolete in ('offline_hash_bloom.bin',):
        p = os.path.join(BUNDLE, obsolete)
        if os.path.isfile(p):
            os.remove(p)
            print(f'[bundle] eliminado {obsolete}')

    total = sum(
        os.path.getsize(os.path.join(dp, f))
        for dp, _, files in os.walk(BUNDLE)
        for f in files
    )
    print(f'[bundle] Total bundle: {total / (1024 * 1024):.2f} MB')


if __name__ == '__main__':
    main()
