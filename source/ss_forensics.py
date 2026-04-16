"""
ss_forensics.py — Forensic techniques for Minecraft Prison SS inspections.

Implements the standard manual SS checklist:
  • USN Journal (deleted / created / renamed / prefetch-deleted)
  • AppCompatFlags Store (everything that ever ran on the PC)
  • UserAssist (recently used programs, timestamps, run counts)
  • WinRAR ArcHistory (recently opened RAR archives)
  • DPS service check (stopped = possible ghost client indicator)
  • USBSTOR (USB storage devices ever connected)
  • ComDlg32 OpenSaveMRU (files recently opened/saved via dialogs)
  • Command Processor AutoRun (suspicious custom command hooks)
  • DisallowRun / RestrictRun (blocked applications — evasion attempt)
  • FeatureUsage / AppSwitched (recently alt-tabbed applications)
  • xinputhid service (XInput HID — input manipulation)
  • Tcpip interface parameters (network modifications)
  • MountedDevices (all volumes ever mounted)
  • Prefetch full analysis (run count + last run + DLL list header)
"""

import os
import re
import codecs
import struct
import subprocess
import winreg
from datetime import datetime, timedelta

# ── Known hack / cheat / autoclick name patterns ─────────────────────────────
HACK_PATTERNS = [
    'vape', 'vapelite', 'entropy', 'whiteout', 'liquidbounce', 'wurst',
    'impact', 'sigma', 'flux', 'future', 'astolfo', 'exhibition', 'novoline',
    'rise', 'moon', 'drip', 'phobos', 'komat', 'wasp', 'konas', 'seppuku',
    'sloth', 'lucid', 'tenacity', 'nyx', 'vanish', 'ploow', 'nextgen',
    'zeroday', 'ghost', 'bypass', 'stealth', 'undetected', 'injector',
    'inject', 'dllinjector', 'killaura', 'aimbot', 'triggerbot', 'autoclick',
    'autoclicker', 'jitter', 'clickbot', 'ghostmouse', 'macro', 'ahk',
    'autohotkey', 'cpstool', 'weightclick', 'rapidclick', 'cheat', 'hack',
    'xray', 'scaffold', 'fly', 'bhop', 'nofall', 'reach', 'velocity',
    'wtap', 'aimassist', 'tinytools', 'tiny_tools',
]

# Extensions to watch in USN journal
WATCH_EXTENSIONS = {'.exe', '.jar', '.dll', '.bat', '.ps1', '.vbs', '.py', '.class'}

FILETIME_EPOCH = datetime(1601, 1, 1)


def _ft_to_dt(ft: int) -> datetime:
    """Windows FILETIME (100-ns ticks since 1601-01-01 UTC) → datetime."""
    return FILETIME_EPOCH + timedelta(microseconds=ft // 10)


def _rot13(s: str) -> str:
    return codecs.decode(s, 'rot_13')


def _is_hack(name: str) -> bool:
    n = name.lower()
    return any(p in n for p in HACK_PATTERNS)


class SSForensics:
    """
    Run all manual-SS forensic checks and return a list of findings.
    Each finding is a dict compatible with the main scanner's issue format.
    """

    def __init__(self):
        self._now = datetime.now()
        self._now_utc = datetime.utcnow()

    def scan_all(self) -> list:
        """Run every forensic check. Returns combined findings list."""
        findings = []
        methods = [
            self._scan_usn_journal,
            self._scan_appcompat_store,
            self._scan_userassist,
            self._scan_winrar_history,
            self._scan_dps_service,
            self._scan_usbstor,
            self._scan_comdlg32_mru,
            self._scan_command_processor,
            self._scan_disallow_run,
            self._scan_featureusage,
            self._scan_xinputhid,
            self._scan_mounted_devices,
            self._scan_prefetch_analysis,
            self._scan_tcpip_interfaces,
        ]
        for fn in methods:
            try:
                result = fn()
                if result:
                    findings.extend(result)
                    print(f"[SSForensics] {fn.__name__}: {len(result)} hallazgo(s)")
            except Exception as e:
                print(f"[SSForensics] {fn.__name__} error: {e}")
        return findings

    # =========================================================================
    # 1. USN JOURNAL — deleted / created / renamed exes & prefetch
    # =========================================================================

    def _scan_usn_journal(self) -> list:
        """
        Parse NTFS USN Change Journal via 'fsutil usn readjournal c: csv'.
        Detects:
          0x80000200  FILE_DELETE  — exe/jar/dll deleted
          0x00000100  FILE_CREATE  — exe created
          0x00001000  RENAME_OLD_NAME — exe renamed (old name)
          0x00002000  RENAME_NEW_NAME — exe renamed (new name)
          .pf deleted — prefetch files deleted (anti-forensics!)
        """
        findings = []

        REASONS = {
            '0x80000200': ('DELETED',       'eliminado',    'CRITICAL'),
            '0x00000100': ('CREATED',        'creado',       'SOSPECHOSO'),
            '0x00001000': ('RENAMED_OLD',    'renombrado (nombre viejo)', 'SOSPECHOSO'),
            '0x00002000': ('RENAMED_NEW',    'renombrado (nombre nuevo)', 'SOSPECHOSO'),
        }

        try:
            proc = subprocess.run(
                ['fsutil', 'usn', 'readjournal', 'C:', 'csv'],
                capture_output=True, text=True, timeout=30
            )
            lines = proc.stdout.splitlines()
        except (subprocess.TimeoutExpired, FileNotFoundError, OSError):
            return []

        # CSV columns vary by Windows version but filename is always present
        # Format: "filename","reason","timestamp",...
        # We just scan line by line for reason codes and extensions

        deleted_pf = []

        for line in lines:
            line_lower = line.lower()

            # ── Deleted prefetch files (.pf) ────────────────────────────────
            if '.pf' in line_lower and '0x80000200' in line_lower:
                # Extract filename (first quoted token)
                m = re.search(r'"([^"]+\.pf)"', line, re.IGNORECASE)
                fname = m.group(1) if m else 'prefetch_file.pf'
                deleted_pf.append(fname)
                # If prefetch was deleted → anti-forensics attempt
                findings.append({
                    'tipo':        'USN_PREFETCH_DELETED',
                    'nombre':      f'Prefetch eliminado: {fname}',
                    'ruta':        'USN Journal (C:)',
                    'detalle':     f'Archivo .pf borrado: {fname}',
                    'alerta':      'CRITICAL',
                    'categoria':   'USN_FORENSICS',
                    'descripcion': (
                        f'El archivo Prefetch "{fname}" fue eliminado. '
                        'Borrar Prefetch manualmente es una técnica de anti-forensics '
                        'para ocultar la ejecución de herramientas de cheat/autoclick. '
                        'Windows no borra estos archivos automáticamente.'
                    ),
                })
                continue

            # ── EXE / JAR / DLL events ──────────────────────────────────────
            has_ext = any(ext in line_lower for ext in WATCH_EXTENSIONS)
            if not has_ext:
                continue

            matched_reason = None
            for code, info in REASONS.items():
                if code in line_lower:
                    matched_reason = (code, info)
                    break
            if not matched_reason:
                continue

            # Extract filename
            m = re.search(r'"([^"]+\.(exe|jar|dll|bat|ps1|vbs|py|class))"',
                          line, re.IGNORECASE)
            if not m:
                continue
            fname = m.group(1)

            reason_code, (reason_type, reason_label, base_severity) = matched_reason
            is_hack_name = _is_hack(fname)

            # Only flag: (a) known hack names always, (b) deleted/renamed non-system always
            if not is_hack_name and reason_type == 'CREATED':
                continue   # too many false positives for generic creates

            severity = 'CRITICAL' if is_hack_name else base_severity

            findings.append({
                'tipo':        f'USN_{reason_type}',
                'nombre':      f'USN {reason_label}: {fname}',
                'ruta':        'USN Journal (C:)',
                'detalle':     f'Archivo {reason_label}: {fname} | Razón: {reason_code}',
                'alerta':      severity,
                'categoria':   'USN_FORENSICS',
                'descripcion': (
                    f'El USN Journal del sistema registró que el archivo "{fname}" fue '
                    f'{reason_label}. '
                    + (f'El nombre coincide con patrones de hack conocidos. ' if is_hack_name else '')
                    + 'El USN Journal es un registro de nivel de sistema de archivos NTFS '
                    'que persiste independientemente de si el archivo fue borrado.'
                ),
            })

        return findings

    # =========================================================================
    # 2. AppCompatFlags — Compatibility Assistant Store
    # =========================================================================

    def _scan_appcompat_store(self) -> list:
        """
        HKCU\\SOFTWARE\\Microsoft\\Windows NT\\CurrentVersion\\AppCompatFlags\\
                        Compatibility Assistant\\Store
        Contains EVERY executable that ever ran on the PC — even deleted ones.
        Values are full paths to executables. Look for hack/autoclick names.
        """
        findings = []
        key_path = (r'SOFTWARE\Microsoft\Windows NT\CurrentVersion'
                    r'\AppCompatFlags\Compatibility Assistant\Store')
        try:
            with winreg.OpenKey(winreg.HKEY_CURRENT_USER, key_path) as key:
                i = 0
                while True:
                    try:
                        val_name, val_data, _ = winreg.EnumValue(key, i)
                    except OSError:
                        break
                    i += 1
                    if not _is_hack(val_name):
                        continue
                    findings.append({
                        'tipo':        'APPCOMPAT_HACK',
                        'nombre':      f'AppCompat: {os.path.basename(val_name)}',
                        'ruta':        val_name,
                        'detalle':     f'Ruta completa en AppCompat Store: {val_name}',
                        'alerta':      'CRITICAL',
                        'categoria':   'APPCOMPAT',
                        'descripcion': (
                            f'AppCompatFlags Store registra que "{val_name}" fue ejecutado en este PC. '
                            'Esta clave existe AUNQUE el archivo haya sido eliminado. '
                            'El jugador no puede borrarla sin herramientas avanzadas.'
                        ),
                    })
        except OSError:
            pass
        return findings

    # =========================================================================
    # 3. UserAssist — recently used programs (ROT13 encoded, with timestamps)
    # =========================================================================

    def _scan_userassist(self) -> list:
        """
        HKCU\\Software\\Microsoft\\Windows\\CurrentVersion\\Explorer\\UserAssist
        Values are ROT13-encoded program paths. Binary data contains:
          Offset 0x08: DWORD run count
          Offset 0x3C: QWORD FILETIME last run
        """
        findings = []
        base_path = r'Software\Microsoft\Windows\CurrentVersion\Explorer\UserAssist'
        try:
            with winreg.OpenKey(winreg.HKEY_CURRENT_USER, base_path) as ua:
                gi = 0
                while True:
                    try:
                        guid = winreg.EnumKey(ua, gi)
                    except OSError:
                        break
                    gi += 1
                    try:
                        with winreg.OpenKey(ua, guid + r'\Count') as count_key:
                            vi = 0
                            while True:
                                try:
                                    enc_name, val_data, _ = winreg.EnumValue(count_key, vi)
                                except OSError:
                                    break
                                vi += 1
                                try:
                                    decoded = _rot13(enc_name)
                                except Exception:
                                    decoded = enc_name

                                if not _is_hack(decoded):
                                    continue

                                # Parse binary data for run count and last-run time
                                run_count = 0
                                last_run  = None
                                if isinstance(val_data, bytes) and len(val_data) >= 72:
                                    try:
                                        run_count = struct.unpack_from('<I', val_data, 8)[0]
                                        ft        = struct.unpack_from('<Q', val_data, 60)[0]
                                        if ft > 0:
                                            last_run = _ft_to_dt(ft)
                                    except Exception:
                                        pass

                                last_str = (last_run.strftime('%Y-%m-%d %H:%M')
                                            if last_run else 'desconocido')
                                delta_h  = ((self._now_utc - last_run).total_seconds() / 3600
                                            if last_run else 999)
                                severity = 'CRITICAL' if delta_h < 24 else 'SOSPECHOSO'

                                findings.append({
                                    'tipo':        'USERASSIST_HACK',
                                    'nombre':      f'UserAssist: {os.path.basename(decoded)} ({run_count}x)',
                                    'ruta':        decoded,
                                    'detalle':     (
                                        f'Ejecutado {run_count} veces — '
                                        f'última vez: {last_str} UTC ({int(delta_h)}h antes)'
                                    ),
                                    'alerta':      severity,
                                    'categoria':   'USERASSIST',
                                    'descripcion': (
                                        f'UserAssist indica que "{decoded}" fue ejecutado {run_count} veces, '
                                        f'última vez hace {int(delta_h)}h. '
                                        'UserAssist persiste aunque el ejecutable sea eliminado.'
                                    ),
                                })
                    except OSError:
                        continue
        except OSError:
            pass
        return findings

    # =========================================================================
    # 4. WinRAR ArcHistory — recently opened RAR archives
    # =========================================================================

    def _scan_winrar_history(self) -> list:
        """
        HKCU\\SOFTWARE\\WinRAR\\ArcHistory
        Lists recently opened RAR/ZIP archives. Look for hack-related names.
        """
        findings = []
        try:
            with winreg.OpenKey(winreg.HKEY_CURRENT_USER,
                                r'SOFTWARE\WinRAR\ArcHistory') as key:
                i = 0
                while True:
                    try:
                        _, path, _ = winreg.EnumValue(key, i)
                    except OSError:
                        break
                    i += 1
                    if not _is_hack(str(path)):
                        continue
                    findings.append({
                        'tipo':        'WINRAR_HACK_ARCHIVE',
                        'nombre':      f'WinRAR history: {os.path.basename(str(path))}',
                        'ruta':        str(path),
                        'detalle':     f'Archivo RAR abierto recientemente: {path}',
                        'alerta':      'CRITICAL',
                        'categoria':   'WINRAR',
                        'descripcion': (
                            f'WinRAR registra que el archivo "{path}" fue abierto recientemente. '
                            'El nombre coincide con patrones de hack. '
                            'Aunque el archivo haya sido borrado, el historial persiste.'
                        ),
                    })
        except OSError:
            pass
        return findings

    # =========================================================================
    # 5. DPS Service — stopped = possible ghost client
    # =========================================================================

    def _scan_dps_service(self) -> list:
        """
        sc query dps  — Diagnostic Policy Service
        If STOPPED: player may have disabled it to hide activity
        (common ghost client technique; some also disable it via autorun).
        """
        findings = []
        try:
            result = subprocess.run(
                ['sc', 'query', 'dps'],
                capture_output=True, text=True, timeout=10
            )
            output = result.stdout.lower()
            if 'stopped' in output:
                findings.append({
                    'tipo':        'DPS_SERVICE_STOPPED',
                    'nombre':      'Servicio DPS (Diagnostic Policy) DETENIDO',
                    'ruta':        'sc query dps',
                    'detalle':     'STATE: STOPPED — el servicio de diagnóstico de Windows está desactivado',
                    'alerta':      'CRITICAL',
                    'categoria':   'SERVICES',
                    'descripcion': (
                        'El servicio DPS (Diagnostic Policy Service) está DETENIDO. '
                        'Este servicio es necesario para el diagnóstico normal del sistema. '
                        'Algunos ghost clients y bypasses lo deshabilitan para ocultar '
                        'actividad anormal o evitar registros del sistema. '
                        'Un usuario normal nunca lo detiene.'
                    ),
                })
            elif 'running' in output:
                pass   # normal
            else:
                findings.append({
                    'tipo':        'DPS_SERVICE_UNKNOWN',
                    'nombre':      'Servicio DPS en estado desconocido',
                    'ruta':        'sc query dps',
                    'detalle':     output.strip()[:120],
                    'alerta':      'SOSPECHOSO',
                    'categoria':   'SERVICES',
                    'descripcion': 'El servicio DPS no responde normalmente. Puede haber sido manipulado.',
                })
        except (subprocess.TimeoutExpired, FileNotFoundError, OSError):
            pass
        return findings

    # =========================================================================
    # 6. USBSTOR — USB storage devices ever connected
    # =========================================================================

    def _scan_usbstor(self) -> list:
        """
        HKLM\\SYSTEM\\CurrentControlSet\\Enum\\USBSTOR
        Lists every USB storage device ever connected. Useful for:
        - Finding external drives used to transfer hacks
        - Cross-referencing with other findings
        """
        findings = []
        try:
            with winreg.OpenKey(winreg.HKEY_LOCAL_MACHINE,
                                r'SYSTEM\CurrentControlSet\Enum\USBSTOR') as usb:
                i = 0
                while True:
                    try:
                        dev_class = winreg.EnumKey(usb, i)
                    except OSError:
                        break
                    i += 1
                    try:
                        with winreg.OpenKey(usb, dev_class) as cls_key:
                            j = 0
                            while True:
                                try:
                                    instance = winreg.EnumKey(cls_key, j)
                                except OSError:
                                    break
                                j += 1
                                try:
                                    with winreg.OpenKey(cls_key, instance) as inst_key:
                                        try:
                                            friendly, _ = winreg.QueryValueEx(inst_key, 'FriendlyName')
                                        except OSError:
                                            friendly = dev_class

                                        info = winreg.QueryInfoKey(inst_key)
                                        ft   = info[2]
                                        last = _ft_to_dt(ft)
                                        delta_h = (self._now_utc - last).total_seconds() / 3600

                                        if delta_h > 72:
                                            continue   # only report recent (72h)

                                        findings.append({
                                            'tipo':        'USBSTOR_DEVICE',
                                            'nombre':      f'USB Storage: {friendly}',
                                            'ruta':        f'HKLM\\SYSTEM\\...\\USBSTOR\\{dev_class}',
                                            'detalle':     (
                                                f'Dispositivo: {friendly}\n'
                                                f'Última actividad: {last.strftime("%Y-%m-%d %H:%M")} UTC '
                                                f'(hace {int(delta_h)}h)'
                                            ),
                                            'alerta':      'SOSPECHOSO' if delta_h < 6 else 'POCO_SOSPECHOSO',
                                            'categoria':   'USB_FORENSICS',
                                            'descripcion': (
                                                f'Dispositivo de almacenamiento USB "{friendly}" '
                                                f'conectado hace {int(delta_h)}h. '
                                                'Los jugadores suelen usar USB para transferir hacks '
                                                'y evitar que aparezcan en el historial del navegador.'
                                            ),
                                        })
                                except OSError:
                                    continue
                    except OSError:
                        continue
        except OSError:
            pass
        return findings

    # =========================================================================
    # 7. ComDlg32 OpenSaveMRU — recently opened/saved files via dialogs
    # =========================================================================

    def _scan_comdlg32_mru(self) -> list:
        """
        HKCU\\SOFTWARE\\Microsoft\\Windows\\CurrentVersion\\Explorer\\
               ComDlg32\\OpenSavePidlMRU
        Records files recently opened or saved via Windows file dialog.
        Look for hack-related file names in MRU entries.
        """
        findings = []
        try:
            base = (r'SOFTWARE\Microsoft\Windows\CurrentVersion\Explorer'
                    r'\ComDlg32\OpenSavePidlMRU')
            with winreg.OpenKey(winreg.HKEY_CURRENT_USER, base) as mru:
                gi = 0
                while True:
                    try:
                        ext_key = winreg.EnumKey(mru, gi)
                    except OSError:
                        break
                    gi += 1
                    try:
                        with winreg.OpenKey(mru, ext_key) as ek:
                            vi = 0
                            while True:
                                try:
                                    val_name, val_data, _ = winreg.EnumValue(ek, vi)
                                except OSError:
                                    break
                                vi += 1
                                if val_name == 'MRUListEx':
                                    continue
                                # PIDL binary — try to extract text fragments
                                if isinstance(val_data, bytes):
                                    try:
                                        text = val_data.decode('utf-16-le', errors='ignore')
                                    except Exception:
                                        text = ''
                                    if _is_hack(text):
                                        m = re.search(r'[\w\-\.]+\.(exe|jar|rar|zip|dll)',
                                                      text, re.IGNORECASE)
                                        fname = m.group(0) if m else text[:60].strip()
                                        findings.append({
                                            'tipo':        'COMDLG32_HACK',
                                            'nombre':      f'OpenSave MRU: {fname}',
                                            'ruta':        f'ComDlg32\\{ext_key}',
                                            'detalle':     f'Archivo abierto/guardado recientemente: {fname}',
                                            'alerta':      'SOSPECHOSO',
                                            'categoria':   'MRU_FORENSICS',
                                            'descripcion': (
                                                f'El diálogo de apertura/guardado de Windows registra '
                                                f'que "{fname}" fue seleccionado recientemente. '
                                                'Indica que el jugador abrió o guardó un archivo '
                                                'con nombre de hack mediante un diálogo de Windows.'
                                            ),
                                        })
                    except OSError:
                        continue
        except OSError:
            pass
        return findings

    # =========================================================================
    # 8. Command Processor AutoRun — suspicious custom hooks
    # =========================================================================

    def _scan_command_processor(self) -> list:
        """
        HKLM\\SOFTWARE\\Microsoft\\Command Processor → AutoRun
        If set, every CMD session runs this command first.
        Used by some cheats to hook or load things silently.
        """
        findings = []
        try:
            with winreg.OpenKey(winreg.HKEY_LOCAL_MACHINE,
                                r'SOFTWARE\Microsoft\Command Processor') as key:
                try:
                    autorun, _ = winreg.QueryValueEx(key, 'AutoRun')
                    if autorun and str(autorun).strip():
                        findings.append({
                            'tipo':        'CMD_AUTORUN',
                            'nombre':      f'Command Processor AutoRun configurado',
                            'ruta':        r'HKLM\SOFTWARE\Microsoft\Command Processor',
                            'detalle':     f'AutoRun = "{autorun}"',
                            'alerta':      'CRITICAL',
                            'categoria':   'AUTORUN',
                            'descripcion': (
                                f'El Command Processor tiene un AutoRun configurado: "{autorun}". '
                                'Esto significa que CADA VEZ que se abre CMD, '
                                'este comando se ejecuta automáticamente. '
                                'Algunos ghost clients y hooks usan este mecanismo para '
                                'cargarse de forma persistente.'
                            ),
                        })
                except OSError:
                    pass   # no AutoRun value = normal
        except OSError:
            pass

        # Also check HKCU
        try:
            with winreg.OpenKey(winreg.HKEY_CURRENT_USER,
                                r'SOFTWARE\Microsoft\Command Processor') as key:
                try:
                    autorun, _ = winreg.QueryValueEx(key, 'AutoRun')
                    if autorun and str(autorun).strip():
                        findings.append({
                            'tipo':        'CMD_AUTORUN_HKCU',
                            'nombre':      f'Command Processor AutoRun (usuario) configurado',
                            'ruta':        r'HKCU\SOFTWARE\Microsoft\Command Processor',
                            'detalle':     f'AutoRun = "{autorun}"',
                            'alerta':      'CRITICAL',
                            'categoria':   'AUTORUN',
                            'descripcion': (
                                f'AutoRun en CMD para el usuario actual: "{autorun}". '
                                'Indica posible hook persistente de ghost client.'
                            ),
                        })
                except OSError:
                    pass
        except OSError:
            pass

        return findings

    # =========================================================================
    # 9. DisallowRun / RestrictRun — blocked applications
    # =========================================================================

    def _scan_disallow_run(self) -> list:
        """
        HKCU\\Software\\Microsoft\\Windows\\CurrentVersion\\Policies\\Explorer\\DisallowRun
        HKCU\\...\\RestrictRun
        If a player blocked specific apps (e.g., Process Hacker, Wireshark),
        that itself is suspicious evidence of trying to hide something.
        """
        findings = []
        SUSPICIOUS_BLOCKED = [
            'processhacker', 'process hacker', 'procexp', 'procmon',
            'wireshark', 'fiddler', 'charles', 'tcpview',
            'autoruns', 'regshot', 'regmon',
            'anydesk', 'teamviewer',   # blocking SS tools is VERY suspicious
        ]
        policies = [
            (winreg.HKEY_CURRENT_USER,
             r'Software\Microsoft\Windows\CurrentVersion\Policies\Explorer\DisallowRun',
             'DisallowRun'),
            (winreg.HKEY_CURRENT_USER,
             r'Software\Microsoft\Windows\CurrentVersion\Policies\Explorer\RestrictRun',
             'RestrictRun'),
        ]
        for hive, path, policy_name in policies:
            try:
                with winreg.OpenKey(hive, path) as key:
                    i = 0
                    blocked_apps = []
                    while True:
                        try:
                            _, val, _ = winreg.EnumValue(key, i)
                        except OSError:
                            break
                        i += 1
                        blocked_apps.append(str(val).lower())

                    if not blocked_apps:
                        continue

                    # Check if any suspicious tools are blocked
                    hit = [app for app in blocked_apps
                           if any(s in app for s in SUSPICIOUS_BLOCKED)]

                    # Report any blocked apps (being selective is itself suspicious)
                    all_blocked_str = ', '.join(blocked_apps[:10])
                    severity = 'CRITICAL' if hit else 'SOSPECHOSO'
                    findings.append({
                        'tipo':        f'POLICY_{policy_name.upper()}',
                        'nombre':      f'{policy_name}: {len(blocked_apps)} app(s) bloqueada(s)',
                        'ruta':        path,
                        'detalle':     f'Apps bloqueadas: {all_blocked_str}',
                        'alerta':      severity,
                        'categoria':   'POLICY_FORENSICS',
                        'descripcion': (
                            f'La política {policy_name} bloquea la ejecución de: {all_blocked_str}. '
                            + (f'Herramientas de análisis bloqueadas: {", ".join(hit)}. ' if hit else '')
                            + 'Bloquear herramientas de análisis o SS es fuertemente sospechoso.'
                        ),
                    })
            except OSError:
                continue

        return findings

    # =========================================================================
    # 10. FeatureUsage / AppSwitched — recently alt-tabbed apps
    # =========================================================================

    def _scan_featureusage(self) -> list:
        """
        HKCU\\SOFTWARE\\Microsoft\\Windows\\CurrentVersion\\Explorer\\
               FeatureUsage\\AppSwitched
        Records apps the user alt-tabbed to recently. Look for hack/cheat names.
        (Not available on all Windows versions.)
        """
        findings = []
        try:
            key_path = (r'SOFTWARE\Microsoft\Windows\CurrentVersion\Explorer'
                        r'\FeatureUsage\AppSwitched')
            with winreg.OpenKey(winreg.HKEY_CURRENT_USER, key_path) as key:
                i = 0
                while True:
                    try:
                        val_name, val_data, _ = winreg.EnumValue(key, i)
                    except OSError:
                        break
                    i += 1
                    if not _is_hack(val_name):
                        continue
                    count = val_data if isinstance(val_data, int) else 0
                    findings.append({
                        'tipo':        'APPSWITCHED_HACK',
                        'nombre':      f'AppSwitched: {val_name} ({count}x alt-tab)',
                        'ruta':        key_path,
                        'detalle':     f'Aplicación: {val_name} — alt-tabbed {count} veces',
                        'alerta':      'CRITICAL',
                        'categoria':   'APPSWITCHED',
                        'descripcion': (
                            f'FeatureUsage registra que el usuario hizo alt-tab a "{val_name}" '
                            f'{count} veces. El nombre coincide con patrones de hack. '
                            'Indica que la aplicación estaba activa durante la sesión.'
                        ),
                    })
        except OSError:
            pass
        return findings

    # =========================================================================
    # 11. xinputhid — XInput HID service
    # =========================================================================

    def _scan_xinputhid(self) -> list:
        """
        HKLM\\SYSTEM\\CurrentControlSet\\Services\\xinputhid
        XInput HID service. Check its state and startup type.
        Some cheat tools manipulate this service.
        """
        findings = []
        try:
            with winreg.OpenKey(winreg.HKEY_LOCAL_MACHINE,
                                r'SYSTEM\CurrentControlSet\Services\xinputhid') as key:
                try:
                    start_type, _ = winreg.QueryValueEx(key, 'Start')
                    # 0=Boot, 1=System, 2=Auto, 3=Manual, 4=Disabled
                    if start_type == 4:
                        findings.append({
                            'tipo':        'XINPUTHID_DISABLED',
                            'nombre':      'Servicio xinputhid DESHABILITADO',
                            'ruta':        r'HKLM\SYSTEM\CurrentControlSet\Services\xinputhid',
                            'detalle':     'Start = 4 (Disabled) — XInput HID deshabilitado',
                            'alerta':      'SOSPECHOSO',
                            'categoria':   'SERVICES',
                            'descripcion': (
                                'El servicio XInput HID está deshabilitado. '
                                'Algunos programas de manipulación de input lo deshabilitan '
                                'para interceptar señales del mouse a nivel más bajo.'
                            ),
                        })
                    try:
                        image_path, _ = winreg.QueryValueEx(key, 'ImagePath')
                        if image_path and _is_hack(str(image_path)):
                            findings.append({
                                'tipo':        'XINPUTHID_MODIFIED',
                                'nombre':      f'xinputhid ImagePath sospechoso: {image_path}',
                                'ruta':        r'HKLM\SYSTEM\CurrentControlSet\Services\xinputhid',
                                'detalle':     f'ImagePath = {image_path}',
                                'alerta':      'CRITICAL',
                                'categoria':   'SERVICES',
                                'descripcion': (
                                    f'El servicio xinputhid apunta a una ruta sospechosa: "{image_path}". '
                                    'Esto indica posible modificación del driver de entrada.'
                                ),
                            })
                    except OSError:
                        pass
                except OSError:
                    pass
        except OSError:
            pass
        return findings

    # =========================================================================
    # 12. MountedDevices — all volumes ever mounted
    # =========================================================================

    def _scan_mounted_devices(self) -> list:
        """
        HKLM\\SYSTEM\\MountedDevices
        Records all drive letters/volumes ever mounted. Useful to know
        if external drives were connected (could have held hacks).
        This is a summary — report count of non-standard entries.
        """
        findings = []
        try:
            with winreg.OpenKey(winreg.HKEY_LOCAL_MACHINE,
                                r'SYSTEM\MountedDevices') as key:
                i = 0
                non_system = []
                while True:
                    try:
                        val_name, _, _ = winreg.EnumValue(key, i)
                    except OSError:
                        break
                    i += 1
                    # Skip standard system volumes (C:, etc.)
                    if re.match(r'\\DosDevices\\[CD]:', val_name, re.IGNORECASE):
                        continue
                    if '\\DosDevices\\' in val_name:
                        non_system.append(val_name)

                if non_system:
                    findings.append({
                        'tipo':        'MOUNTED_DEVICES_EXTRA',
                        'nombre':      f'MountedDevices: {len(non_system)} volumen(es) extra',
                        'ruta':        r'HKLM\SYSTEM\MountedDevices',
                        'detalle':     ', '.join(non_system[:10]),
                        'alerta':      'POCO_SOSPECHOSO',
                        'categoria':   'USB_FORENSICS',
                        'descripcion': (
                            f'Se encontraron {len(non_system)} volumen(es) no estándar en MountedDevices: '
                            f'{", ".join(non_system[:5])}. '
                            'Indica que se conectaron unidades externas adicionales.'
                        ),
                    })
        except OSError:
            pass
        return findings

    # =========================================================================
    # 13. Prefetch full analysis — run count, last run, referenced files
    # =========================================================================

    def _scan_prefetch_analysis(self) -> list:
        """
        Scan C:\\Windows\\Prefetch\\ for all .pf files:
          - Report run count and last-run timestamp from filename metadata
          - Flag hack/autoclick tool names
          - Flag files with modification timestamps < 2h (very recently used)

        Prefetch files survive executable deletion.
        """
        findings = []
        prefetch_dir = r'C:\Windows\Prefetch'
        if not os.path.exists(prefetch_dir):
            return []

        now = datetime.now()
        try:
            entries = os.listdir(prefetch_dir)
        except PermissionError:
            return []

        for fname in entries:
            if not fname.upper().endswith('.PF'):
                continue

            pf_path = os.path.join(prefetch_dir, fname)
            exe_name = fname.split('-')[0] if '-' in fname else fname[:-3]

            try:
                mtime   = os.path.getmtime(pf_path)
                last_dt = datetime.fromtimestamp(mtime)
                delta_h = (now - last_dt).total_seconds() / 3600
            except OSError:
                last_dt, delta_h = None, 999

            # Try to read run count from .pf binary (Windows 8+, offset 0x90 = uint32)
            run_count = None
            try:
                with open(pf_path, 'rb') as f:
                    data = f.read(0xA0)
                if len(data) >= 0x94:
                    run_count = struct.unpack_from('<I', data, 0x90)[0]
            except Exception:
                pass

            is_hack_name = _is_hack(exe_name)

            if not is_hack_name and delta_h > 4:
                continue   # only report recent non-hack prefetches

            severity = ('CRITICAL' if is_hack_name and delta_h < 2
                        else 'SOSPECHOSO' if is_hack_name
                        else 'POCO_SOSPECHOSO')

            count_str = f', {run_count} veces ejecutado' if run_count else ''
            findings.append({
                'tipo':        'PREFETCH_ANALYSIS',
                'nombre':      f'Prefetch: {exe_name}{count_str}',
                'ruta':        pf_path,
                'detalle':     (
                    f'Archivo: {fname}\n'
                    f'Última modificación: {last_dt.strftime("%Y-%m-%d %H:%M") if last_dt else "?"} '
                    f'(hace {int(delta_h)}h)'
                    + (f' | Veces ejecutado: {run_count}' if run_count else '')
                ),
                'alerta':      severity,
                'categoria':   'PREFETCH',
                'descripcion': (
                    f'"{exe_name}" aparece en Prefetch'
                    + (f' — ejecutado {run_count} veces' if run_count else '')
                    + f', última vez hace {int(delta_h)}h. '
                    + ('El nombre coincide con patrones de hack/autoclick. ' if is_hack_name else
                       'Ejecutado muy recientemente. ')
                    + 'El archivo Prefetch sobrevive al borrado del ejecutable.'
                ),
            })

        return findings

    # =========================================================================
    # 14. Tcpip Interfaces — network interface modifications
    # =========================================================================

    def _scan_tcpip_interfaces(self) -> list:
        """
        HKLM\\SYSTEM\\CurrentControlSet\\Services\\Tcpip\\Parameters\\Interfaces
        Check for custom DNS or suspicious interface modifications
        (some bypass tools inject custom DNS to avoid detection).
        """
        findings = []
        SUSPICIOUS_DNS = ['8.8.8.8', '1.1.1.1']  # override from ISP = possible bypass
        try:
            with winreg.OpenKey(winreg.HKEY_LOCAL_MACHINE,
                                r'SYSTEM\CurrentControlSet\Services\Tcpip\Parameters\Interfaces') as ifaces:
                i = 0
                while True:
                    try:
                        iface_guid = winreg.EnumKey(ifaces, i)
                    except OSError:
                        break
                    i += 1
                    try:
                        with winreg.OpenKey(ifaces, iface_guid) as iface:
                            for dns_val in ('NameServer', 'DhcpNameServer'):
                                try:
                                    dns, _ = winreg.QueryValueEx(iface, dns_val)
                                    if dns and dns.strip():
                                        findings.append({
                                            'tipo':        'TCPIP_DNS_OVERRIDE',
                                            'nombre':      f'DNS personalizado: {dns.strip()}',
                                            'ruta':        f'HKLM\\...\\Interfaces\\{iface_guid}',
                                            'detalle':     f'{dns_val} = {dns.strip()}',
                                            'alerta':      'POCO_SOSPECHOSO',
                                            'categoria':   'NETWORK_FORENSICS',
                                            'descripcion': (
                                                f'Interfaz {iface_guid} tiene DNS personalizado: {dns.strip()}. '
                                                'DNS modificado puede indicar bypass de network monitoring.'
                                            ),
                                        })
                                except OSError:
                                    continue
                    except OSError:
                        continue
        except OSError:
            pass
        return findings
