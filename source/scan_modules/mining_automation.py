"""
Tres módulos de detección de automatización de minado (Baritone, macros, bots).
Sin UI — solo análisis pasivo de disco/procesos/registro.
"""
import os
import re
from pathlib import Path


def _issue(nombre, detalle, alerta='SOSPECHOSO', tipo='mining_automation'):
    return {
        'tipo': tipo,
        'nombre': nombre,
        'ruta': '',
        'detalle': detalle,
        'alerta': alerta,
        'categoria': 'MINING_AUTOMATION',
        'confidence': 0.82 if alerta == 'CRITICAL' else 0.68,
    }


def _roots(ctx):
    if hasattr(ctx, 'minecraft_root') and ctx.minecraft_root:
        return [ctx.minecraft_root]
    appdata = os.environ.get('APPDATA', '')
    return [os.path.join(appdata, '.minecraft'), os.path.join(appdata, 'Roaming', '.minecraft')]


def scan_baritone_traces(ctx):
    """Rastros de Baritone / pathfinder en .minecraft y mods."""
    findings = []
    roots = _roots(ctx)
    markers = (
        'baritone', 'pathfinder', 'baritone-api', 'baritonemod',
        'autowalk', 'automine', 'minecommand',
    )
    for root in roots:
        if not root or not os.path.isdir(root):
            continue
        for dirpath, dirnames, filenames in os.walk(root):
            depth = dirpath[len(root):].count(os.sep)
            if depth > 5:
                dirnames[:] = []
                continue
            low_path = dirpath.lower()
            for m in markers:
                if m in low_path:
                    findings.append(_issue(
                        'Rastro de Baritone / minado automático',
                        f'Carpeta o ruta sospechosa: {dirpath}',
                        'CRITICAL' if 'baritone' in low_path else 'SOSPECHOSO',
                    ))
                    break
            for fn in filenames:
                fl = fn.lower()
                if any(m in fl for m in markers) and fl.endswith(('.jar', '.json', '.txt', '.cfg')):
                    findings.append(_issue(
                        'Archivo de minado automático (Baritone)',
                        os.path.join(dirpath, fn),
                        'CRITICAL',
                    ))
            if len(findings) >= 8:
                return findings
    # settings de Baritone en config
    for root in roots:
        for cfg in ('baritone', 'baritone4', 'settings.txt'):
            p = os.path.join(root, cfg)
            if os.path.isdir(p) or (os.path.isfile(p) and 'baritone' in cfg.lower()):
                findings.append(_issue('Configuración Baritone presente', p, 'CRITICAL'))
        mods = os.path.join(root, 'mods')
        if os.path.isdir(mods):
            for fn in os.listdir(mods):
                fl = fn.lower()
                if 'baritone' in fl or 'pathfinder' in fl:
                    findings.append(_issue('Mod JAR de minado automático', os.path.join(mods, fn), 'CRITICAL'))
    return findings


def scan_auto_mine_macros(ctx):
    """Scripts AHK/vbs/bat con patrones de minado automático."""
    findings = []
    patterns = re.compile(
        r'(autoclick|auto.?mine|baritone|mineflayer|nuker|xray|hold.*click|'
        r'loop.*click|send.*\{lbutton\}|block.*break)',
        re.I,
    )
    bases = [
        os.path.join(os.environ.get('USERPROFILE', ''), 'Documents'),
        os.path.join(os.environ.get('APPDATA', ''), 'Microsoft', 'Windows', 'Start Menu', 'Programs', 'Startup'),
        os.path.join(os.environ.get('USERPROFILE', ''), 'Downloads'),
        os.path.join(os.environ.get('APPDATA', ''), 'Roaming', 'Microsoft', 'Windows', 'Recent'),
    ]
    exts = ('.ahk', '.vbs', '.bat', '.cmd', '.ps1', '.lua')
    for base in bases:
        if not base or not os.path.isdir(base):
            continue
        try:
            for p in Path(base).rglob('*'):
                if not p.is_file() or p.suffix.lower() not in exts:
                    continue
                if p.stat().st_size > 512_000:
                    continue
                try:
                    text = p.read_text(encoding='utf-8', errors='ignore')[:8000]
                except Exception:
                    continue
                if patterns.search(text):
                    findings.append(_issue(
                        'Macro/script de minado o autoclick',
                        str(p),
                        'SOSPECHOSO',
                    ))
                if len(findings) >= 6:
                    return findings
        except Exception:
            pass
    return findings


def scan_mining_bot_processes(ctx):
    """Procesos o líneas de comando con bots de minado."""
    findings = []
    try:
        import psutil
    except ImportError:
        return findings

    needles = (
        'baritone', 'mineflayer', 'nodemc', 'minecraftbot',
        'automin', 'nuker', 'orebot', 'stripmine', 'litematica',
        'tweakeroo', 'autofish', 'farmhelper',
    )
    for proc in psutil.process_iter(['name', 'cmdline', 'exe']):
        try:
            name = (proc.info.get('name') or '').lower()
            cmd = ' '.join(proc.info.get('cmdline') or []).lower()
            exe = (proc.info.get('exe') or '').lower()
            blob = f'{name} {cmd} {exe}'
            for n in needles:
                if n in blob:
                    findings.append(_issue(
                        'Proceso relacionado con bot de minado',
                        f'{proc.info.get("name")} — {exe or cmd[:120]}',
                        'CRITICAL' if n in ('baritone', 'mineflayer') else 'SOSPECHOSO',
                    ))
                    break
        except (psutil.NoSuchProcess, psutil.AccessDenied):
            continue
        if len(findings) >= 5:
            break
    return findings
