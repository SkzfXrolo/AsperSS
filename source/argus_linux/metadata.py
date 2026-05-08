"""ArgusScanner Linux — inspector de metadatos.

Filtro adicional para reducir FPs revisando los METADATOS de archivos
sospechosos (no solo el filename). Recomendación del tester Linux:
"si parsean el manifest del JAR, miran la firma y el bytecode, los FPs
caen en picada y los hacks reales suben de score".

Funciones públicas:
    inspect_jar(path)  -> dict con manifest, signing, mod-loader markers,
                          bytecode hints, vendor.
    inspect_elf(path)  -> dict con tipo, arch, stripped, interp, dyn-libs.
    inspect_pe(path)   -> dict mínimo para .exe/.dll que aparezcan en Linux
                          (papelera con archivo Windows arrastrado, etc).
    inspect_file(path) -> router por extensión + magic; devuelve siempre
                          {'kind', 'verdict', 'meta'} donde verdict es uno
                          de 'legit_mod', 'signed_publisher', 'suspicious',
                          'unknown'.

Diseño:
    - Nunca crashea: cualquier excepción → verdict='unknown'.
    - Read-only, no modifica nada.
    - Liviano: usa stdlib (zipfile, struct, hashlib).
    - Pensado para complementar smart_hack_match, NO para reemplazarlo.
"""

from __future__ import annotations

import os
import re
import struct
import zipfile
from typing import Any

# Vendors / loaders / CDNs reconocidos en META-INF/MANIFEST.MF y firmas
LEGIT_MOD_VENDORS = (
    'fabricmc', 'fabric mc', 'fabric mod loader',
    'minecraftforge', 'forge', 'neoforged', 'neoforge', 'neo forged',
    'quiltmc', 'quilt', 'sponge', 'spongepowered',
    'mojang', 'mojang ab', 'mojang studios',
    'optifine', 'optifineteam',
    'jetbrains', 'oracle', 'azul systems', 'amazon corretto',
    'eclipse adoptium', 'temurin',
)
LEGIT_CDN_FRAGMENTS = (
    'curseforge', 'overwolf', 'modrinth', 'cfwidget',
    'creeperhost', 'multimc.org', 'prismlauncher', 'atlauncher',
    'fabricmc', 'minecraftforge', 'neoforged',
)
MOD_LOADER_MARKERS = (
    'fabric.mod.json', 'quilt.mod.json',
    'meta-inf/mods.toml', 'meta-inf/neoforge.mods.toml',
    'mcmod.info',
)

# Bytecode patterns que SUBEN sospecha cuando aparecen en clases del JAR.
# Sincronizado parcialmente con source/main.py (Windows scanner).
HACK_BYTECODE_PATTERNS = (
    b'net/minecraft/client/Minecraft',
    b'net/minecraft/client/MinecraftClient',
    b'net/liquidbounce/', b'meteordevelopment/',
    b'com/github/wurstclient/', b'me/zeroeightsix/',
    b'com/vape/', b'net/sigma/', b'com/aristois/',
    b'me/drip/', b'net/rusherhack/', b'com/entropy/',
    b'KillAura', b'AimBot', b'AimAssist', b'AutoClick',
    b'AutoClicker', b'TriggerBot', b'WallHack', b'XrayClient',
    b'java/lang/instrument/Instrumentation',
)

# Java agents legítimos que NO son hacks (Filter #58 del MEJORAS)
LEGIT_JAVA_AGENTS = (
    'yourkit', 'jprofiler', 'visualvm', 'jrebel',
    'newrelic', 'datadog-agent', 'appdynamics',
    'glowroot', 'kanela', 'pinpoint-agent',
    'aspectjweaver', 'jacocoagent', 'byteman',
    'gradle-agent', 'maven-surefire',
)

_PE_MAGIC      = b'MZ'
_ELF_MAGIC     = b'\x7fELF'
_ZIP_MAGIC     = b'PK\x03\x04'

_MAX_BYTECODE_CLASSES_SCANNED = 80   # límite duro por JAR
_MAX_MANIFEST_BYTES           = 256 * 1024


# ─────────────────────────── helpers ────────────────────────────────────────
def _safe_open(path: str, mode: str = 'rb'):
    try:
        return open(path, mode)
    except OSError:
        return None


def _peek_magic(path: str, n: int = 8) -> bytes:
    f = _safe_open(path)
    if f is None:
        return b''
    try:
        return f.read(n)
    finally:
        f.close()


def _detect_kind(path: str) -> str:
    magic = _peek_magic(path, 4)
    if magic.startswith(_ELF_MAGIC):
        return 'elf'
    if magic.startswith(_PE_MAGIC):
        return 'pe'
    if magic.startswith(_ZIP_MAGIC):
        # zip puede ser jar o appimage o zip plano
        ext = os.path.splitext(path)[1].lower()
        if ext == '.jar':
            return 'jar'
        if ext == '.appimage':
            return 'appimage'
        return 'zip'
    ext = os.path.splitext(path)[1].lower()
    if ext == '.jar':
        return 'jar'
    if ext in ('.so',):
        return 'elf'
    if ext in ('.dll', '.exe'):
        return 'pe'
    return 'other'


# ─────────────────────────── JAR ────────────────────────────────────────────
def inspect_jar(path: str) -> dict[str, Any]:
    """Inspecciona un JAR. Devuelve dict con todos los hallazgos.

    Campos clave:
        mod_loader        : 'fabric'|'quilt'|'forge'|'neoforge'|'legacy'|None
        manifest_vendor   : Implementation-Vendor (lowercased) o ''
        manifest_title    : Implementation-Title o ''
        signed            : True si tiene .SF + .RSA/.DSA/.EC bien formado
        cdn_signed        : True si la firma menciona CurseForge/Modrinth/...
        bytecode_hits     : lista de patrones hack encontrados en clases
        class_count       : cantidad de .class (informativo)
        size_b            : tamaño en bytes
        verdict           : 'legit_mod' | 'suspicious' | 'unknown'
    """
    out: dict[str, Any] = {
        'kind':            'jar',
        'mod_loader':      None,
        'manifest_vendor': '',
        'manifest_title':  '',
        'signed':          False,
        'cdn_signed':      False,
        'bytecode_hits':   [],
        'class_count':     0,
        'size_b':          0,
        'verdict':         'unknown',
        'error':           None,
    }
    try:
        out['size_b'] = os.path.getsize(path)
    except OSError:
        pass
    if not zipfile.is_zipfile(path):
        out['error'] = 'not_a_zip'
        return out

    try:
        with zipfile.ZipFile(path, 'r') as zf:
            namelist = zf.namelist()
            names_lower = {n.lower(): n for n in namelist}

            for marker in MOD_LOADER_MARKERS:
                if marker in names_lower:
                    if 'fabric' in marker:
                        out['mod_loader'] = 'fabric'
                    elif 'quilt' in marker:
                        out['mod_loader'] = 'quilt'
                    elif 'neoforge' in marker:
                        out['mod_loader'] = 'neoforge'
                    elif 'mods.toml' in marker:
                        out['mod_loader'] = 'forge'
                    elif marker == 'mcmod.info':
                        out['mod_loader'] = 'legacy'
                    break

            mf_key = names_lower.get('meta-inf/manifest.mf')
            if mf_key:
                try:
                    raw = zf.read(mf_key)[:_MAX_MANIFEST_BYTES]
                    text = raw.decode('utf-8', errors='ignore')
                    for line in text.splitlines():
                        ll = line.lower()
                        if ll.startswith('implementation-vendor:'):
                            out['manifest_vendor'] = line.split(':', 1)[1].strip().lower()
                        elif ll.startswith('implementation-title:'):
                            out['manifest_title'] = line.split(':', 1)[1].strip().lower()
                        elif ll.startswith('built-by:') and not out['manifest_vendor']:
                            out['manifest_vendor'] = line.split(':', 1)[1].strip().lower()
                except (KeyError, OSError):
                    pass

            sf_files  = [n for n in namelist
                         if n.upper().startswith('META-INF/') and n.upper().endswith('.SF')]
            sig_blocks = [n for n in namelist
                          if n.upper().startswith('META-INF/') and
                          n.upper().rsplit('.', 1)[-1] in ('RSA', 'DSA', 'EC')]
            if sf_files and sig_blocks:
                out['signed'] = True
                for sb in sig_blocks[:2]:
                    try:
                        sig_data = zf.read(sb)[:65536].decode('utf-8', errors='ignore').lower()
                        if any(cdn in sig_data for cdn in LEGIT_CDN_FRAGMENTS):
                            out['cdn_signed'] = True
                            break
                    except (KeyError, OSError):
                        pass

            class_files = [n for n in namelist if n.endswith('.class')]
            out['class_count'] = len(class_files)
            seen_hits: set[str] = set()
            for cf in class_files[:_MAX_BYTECODE_CLASSES_SCANNED]:
                try:
                    bc = zf.read(cf)
                except (KeyError, OSError, RuntimeError):
                    continue
                for pat in HACK_BYTECODE_PATTERNS:
                    if pat in bc:
                        token = pat.decode('latin-1').replace('/', '.').rstrip('.')
                        seen_hits.add(token[:60])
                        if len(seen_hits) >= 6:
                            break
                if len(seen_hits) >= 6:
                    break
            out['bytecode_hits'] = sorted(seen_hits)
    except (zipfile.BadZipFile, OSError, RuntimeError) as e:
        out['error'] = type(e).__name__

    out['verdict'] = _verdict_for_jar(out)
    return out


def _verdict_for_jar(meta: dict[str, Any]) -> str:
    has_loader  = bool(meta.get('mod_loader'))
    vendor      = meta.get('manifest_vendor', '')
    legit_vend  = any(v in vendor for v in LEGIT_MOD_VENDORS) if vendor else False
    has_hits    = bool(meta.get('bytecode_hits'))
    cdn         = bool(meta.get('cdn_signed'))
    signed      = bool(meta.get('signed'))

    if has_hits:
        return 'suspicious'
    if (has_loader and (cdn or legit_vend)):
        return 'legit_mod'
    if has_loader and signed:
        return 'legit_mod'
    if has_loader:
        return 'unknown'
    if signed and legit_vend:
        return 'legit_mod'
    return 'unknown'


# ─────────────────────────── ELF ────────────────────────────────────────────
def inspect_elf(path: str) -> dict[str, Any]:
    """Parser mínimo de ELF (header + .interp si está accesible).

    Devuelve dict con: arch, bits, type ('exec'|'dyn'|'rel'|'core'),
    interp (path al loader), is_stripped (heurístico por tamaño <128KB sin
    secciones .symtab), error.
    """
    out: dict[str, Any] = {
        'kind':         'elf',
        'arch':         'unknown',
        'bits':         0,
        'elf_type':     'unknown',
        'interp':       '',
        'is_stripped':  None,
        'size_b':       0,
        'verdict':      'unknown',
        'error':        None,
    }
    f = _safe_open(path)
    if f is None:
        out['error'] = 'open_failed'
        return out
    try:
        try:
            out['size_b'] = os.path.getsize(path)
        except OSError:
            pass
        head = f.read(64)
        if not head.startswith(_ELF_MAGIC):
            out['error'] = 'not_elf'
            return out
        ei_class = head[4]
        ei_data  = head[5]
        out['bits'] = 64 if ei_class == 2 else 32 if ei_class == 1 else 0
        endian = '<' if ei_data == 1 else '>'
        try:
            e_type = struct.unpack(endian + 'H', head[16:18])[0]
            e_machine = struct.unpack(endian + 'H', head[18:20])[0]
            out['elf_type'] = {1: 'rel', 2: 'exec', 3: 'dyn', 4: 'core'}.get(e_type, 'unknown')
            out['arch'] = {
                3: 'x86', 62: 'x86_64', 40: 'arm', 183: 'aarch64',
                243: 'riscv', 8: 'mips', 21: 'powerpc',
            }.get(e_machine, f'machine_{e_machine}')
        except struct.error:
            out['error'] = 'truncated_header'

        # .interp string lookup heurístico (busca /lib/ld- en primeros 4KB)
        try:
            f.seek(0)
            blob = f.read(4096)
            m = re.search(rb'(/lib(?:64)?/ld[-A-Za-z0-9./_-]{2,80})\x00', blob)
            if m:
                out['interp'] = m.group(1).decode('latin-1')
        except OSError:
            pass
    finally:
        f.close()

    out['verdict'] = _verdict_for_elf(out)
    return out


def _verdict_for_elf(meta: dict[str, Any]) -> str:
    interp = meta.get('interp', '')
    # Si el interp es el loader estándar de la distro, casi nunca es un hack standalone.
    if interp.startswith('/lib') and 'ld' in interp:
        return 'unknown'
    return 'unknown'


# ─────────────────────────── PE (Windows binary en Linux) ───────────────────
def inspect_pe(path: str) -> dict[str, Any]:
    """Parser mínimo de PE/COFF (.exe / .dll). En Linux solo aparece cuando
    alguien arrastró un binario Windows a la papelera. Devuelve metadata
    superficial — no validamos firma Authenticode acá (eso requiere
    `osslsigncode` que no está siempre instalado)."""
    out: dict[str, Any] = {
        'kind':       'pe',
        'machine':    'unknown',
        'subsystem':  'unknown',
        'is_dll':     False,
        'has_resources': False,
        'size_b':     0,
        'verdict':    'unknown',
        'error':      None,
    }
    try:
        out['size_b'] = os.path.getsize(path)
    except OSError:
        pass
    f = _safe_open(path)
    if f is None:
        out['error'] = 'open_failed'
        return out
    try:
        head = f.read(64)
        if not head.startswith(_PE_MAGIC):
            out['error'] = 'not_pe'
            return out
        if len(head) < 0x3C + 4:
            out['error'] = 'truncated_dos'
            return out
        e_lfanew = struct.unpack('<I', head[0x3C:0x40])[0]
        if e_lfanew <= 0 or e_lfanew > 8 * 1024 * 1024:
            out['error'] = 'bad_e_lfanew'
            return out
        f.seek(e_lfanew)
        sig = f.read(4)
        if sig != b'PE\x00\x00':
            out['error'] = 'no_pe_sig'
            return out
        coff = f.read(20)
        if len(coff) < 20:
            out['error'] = 'truncated_coff'
            return out
        machine, _nsec, _ts, _, _, _, characteristics = struct.unpack('<HHIIIHH', coff)
        out['machine']   = {0x14c: 'x86', 0x8664: 'x86_64', 0xaa64: 'arm64'}.get(
            machine, f'machine_{machine:#x}')
        out['is_dll']    = bool(characteristics & 0x2000)
        out['has_resources'] = bool(characteristics & 0x0001)
    except (struct.error, OSError) as e:
        out['error'] = type(e).__name__
    finally:
        f.close()

    return out


# ─────────────────────────── router ─────────────────────────────────────────
def inspect_file(path: str) -> dict[str, Any]:
    """Entry point preferido. Detecta el tipo y delega.

    Devuelve siempre un dict con 'kind' y 'verdict' válidos.
    """
    if not path or not os.path.isfile(path):
        return {'kind': 'missing', 'verdict': 'unknown', 'meta': {}}
    kind = _detect_kind(path)
    try:
        if kind == 'jar':
            meta = inspect_jar(path)
        elif kind == 'elf':
            meta = inspect_elf(path)
        elif kind == 'pe':
            meta = inspect_pe(path)
        else:
            meta = {'kind': kind, 'verdict': 'unknown',
                    'size_b': (os.path.getsize(path) if os.path.exists(path) else 0)}
    except Exception as e:
        meta = {'kind': kind, 'verdict': 'unknown', 'error': type(e).__name__}
    return {
        'kind':    meta.get('kind', kind),
        'verdict': meta.get('verdict', 'unknown'),
        'meta':    meta,
    }


def is_legit_java_agent(text: str) -> bool:
    """Filter #58 — True si el texto (filename, manifest, cmdline) contiene
    el nombre de un Java agent legítimo (profilers/APM/build tools)."""
    if not text:
        return False
    t = text.lower()
    return any(a in t for a in LEGIT_JAVA_AGENTS)


__all__ = [
    'inspect_jar', 'inspect_elf', 'inspect_pe', 'inspect_file',
    'is_legit_java_agent',
    'LEGIT_MOD_VENDORS', 'LEGIT_CDN_FRAGMENTS',
    'MOD_LOADER_MARKERS', 'HACK_BYTECODE_PATTERNS',
    'LEGIT_JAVA_AGENTS',
]
