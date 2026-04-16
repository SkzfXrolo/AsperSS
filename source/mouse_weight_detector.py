"""
mouse_weight_detector.py — Detects mouse weight fraud and click-bug in Prison SS context.

The problem: players in "prison" mode place a physical weight on the mouse button
to activate the click-bug (or jitter autoclicking). When they receive an SS request
via AnyDesk they may:
  - Quickly remove the weight before the screenshare connects
  - Disconnect the mouse entirely while the click-bug is active, then reconnect
    right before the SS begins

Detection methods:
  1. Immediate button state check  — button physically held at scanner start
  2. HID registry timestamps       — mouse connected < 20 min before scan
  3. Background device monitor     — mouse plugged/unplugged DURING the session
  4. Click pattern analysis        — mechanical regularity via GetAsyncKeyState polling
"""

import ctypes
import time
import threading
import winreg
from datetime import datetime, timedelta

# ── Win32 constants ─────────────────────────────────────────────────────────
VK_LBUTTON = 0x01
VK_RBUTTON  = 0x02
VK_MBUTTON  = 0x04
try:
    _user32 = ctypes.windll.user32
except Exception:
    _user32 = None

SUSPICION_RECENT_MINUTES = 20   # mouse connected < this → suspicious
_FILETIME_EPOCH = datetime(1601, 1, 1)


def _filetime_to_dt(ft: int) -> datetime:
    """Convert Windows FILETIME (100-ns ticks since 1601-01-01 UTC) → datetime (UTC naive)."""
    return _FILETIME_EPOCH + timedelta(microseconds=ft // 10)


class MouseWeightDetector:
    """
    Detecta fraude de peso sobre el mouse y click-bug en contexto de Prison SS.

    Uso:
        detector = MouseWeightDetector()   # toma snapshot inicial inmediatamente
        detector.start_monitoring()         # lanza hilos de fondo
        ...                                 # (el escaneo corre)
        findings = detector.run_instant_checks()    # verifica estado en el momento
        session  = detector.get_session_findings()  # recolecta lo capturado en fondo
        detector.stop_monitoring()
    """

    def __init__(self):
        self.start_dt              = datetime.now()
        self._monitoring           = False
        self._lock                 = threading.Lock()
        self.device_events         = []   # list of {ts, event, instance, friendly}
        self.click_log             = []   # list of (perf_counter, 'press'|'release', 'L'|'R')
        self._historical_findings  = []   # filled by scan_historical_evidence()

        # Snapshot at construction time (before player can react)
        self.initial_devices       = []
        self.initial_button_states = {}
        try:
            self.initial_devices       = self._enumerate_hid_mice()
            self.initial_button_states = self._get_button_states()
        except Exception as e:
            print(f"[MouseWeightDetector] Init snapshot error: {e}")

    # ── Windows API helpers ──────────────────────────────────────────────────

    @staticmethod
    def _get_button_states() -> dict:
        """Return {left, right, middle} → bool (True = currently pressed)."""
        if _user32 is None:
            return {}
        try:
            g = _user32.GetAsyncKeyState
            return {
                'left':   bool(g(VK_LBUTTON) & 0x8000),
                'right':  bool(g(VK_RBUTTON)  & 0x8000),
                'middle': bool(g(VK_MBUTTON)  & 0x8000),
            }
        except Exception:
            return {}

    @staticmethod
    def _enumerate_hid_mice() -> list:
        """
        Walk HKLM\\SYSTEM\\CurrentControlSet\\Enum\\HID and return all entries
        whose 'Class' value is 'Mouse'.  Each entry: {device_id, instance, friendly, last_write}.
        """
        mice = []
        try:
            with winreg.OpenKey(winreg.HKEY_LOCAL_MACHINE,
                                r"SYSTEM\CurrentControlSet\Enum\HID") as hid:
                i = 0
                while True:
                    try:
                        vid_name = winreg.EnumKey(hid, i)
                    except OSError:
                        break
                    i += 1
                    try:
                        with winreg.OpenKey(hid, vid_name) as vid_key:
                            j = 0
                            while True:
                                try:
                                    inst_name = winreg.EnumKey(vid_key, j)
                                except OSError:
                                    break
                                j += 1
                                try:
                                    with winreg.OpenKey(vid_key, inst_name) as inst_key:
                                        try:
                                            cls, _ = winreg.QueryValueEx(inst_key, "Class")
                                        except OSError:
                                            continue
                                        if str(cls).lower() != "mouse":
                                            continue

                                        # last-write time of the registry key
                                        info       = winreg.QueryInfoKey(inst_key)
                                        last_write = _filetime_to_dt(info[2])

                                        try:
                                            friendly, _ = winreg.QueryValueEx(inst_key, "FriendlyName")
                                            friendly = str(friendly)
                                        except OSError:
                                            friendly = vid_name

                                        mice.append({
                                            'device_id':  vid_name,
                                            'instance':   inst_name,
                                            'friendly':   friendly,
                                            'last_write': last_write,
                                        })
                                except OSError:
                                    continue
                    except OSError:
                        continue
        except Exception as e:
            print(f"[MouseWeightDetector] HID enum error: {e}")
        return mice

    # ── Background monitoring ────────────────────────────────────────────────

    def start_monitoring(self):
        """Start background threads for device-change and click-pattern monitoring."""
        if self._monitoring:
            return
        self._monitoring = True

        t1 = threading.Thread(target=self._device_monitor_loop, daemon=True,
                              name="MouseWeight-DeviceMonitor")
        t2 = threading.Thread(target=self._click_monitor_loop, daemon=True,
                              name="MouseWeight-ClickMonitor")
        t1.start()
        t2.start()

    def stop_monitoring(self):
        self._monitoring = False

    def _device_monitor_loop(self):
        """Poll HID every 2 s; fire CONNECTED/DISCONNECTED events."""
        last_set = {d['instance'] for d in self.initial_devices}

        while self._monitoring:
            try:
                current  = self._enumerate_hid_mice()
                cur_set  = {d['instance'] for d in current}
                added    = cur_set - last_set
                removed  = last_set - cur_set

                with self._lock:
                    for inst in added:
                        friendly = next(
                            (d['friendly'] for d in current if d['instance'] == inst), inst)
                        ev = {'ts': datetime.now(), 'event': 'CONNECTED',
                              'instance': inst, 'friendly': friendly}
                        self.device_events.append(ev)
                        print(f"[MouseWeight] ⚡ Mouse CONECTADO durante SS: {friendly}")

                    for inst in removed:
                        ev = {'ts': datetime.now(), 'event': 'DISCONNECTED',
                              'instance': inst, 'friendly': inst}
                        self.device_events.append(ev)
                        print(f"[MouseWeight] ⚠️  Mouse DESCONECTADO durante SS: {inst}")

                last_set = cur_set
            except Exception:
                pass
            time.sleep(2)

    def _click_monitor_loop(self):
        """
        Poll GetAsyncKeyState every 5 ms and record button transitions.
        Capped at ~60 s worth of data (12,000 samples).
        """
        if _user32 is None:
            return

        prev_l = prev_r = False
        MAX = 12_000

        while self._monitoring:
            try:
                l = bool(_user32.GetAsyncKeyState(VK_LBUTTON) & 0x8000)
                r = bool(_user32.GetAsyncKeyState(VK_RBUTTON) & 0x8000)
                t = time.perf_counter()

                with self._lock:
                    if len(self.click_log) >= MAX:
                        self._monitoring = False  # enough data, stop wasting CPU
                        break

                    if l != prev_l:
                        self.click_log.append((t, 'press' if l else 'release', 'L'))
                        prev_l = l
                    if r != prev_r:
                        self.click_log.append((t, 'press' if r else 'release', 'R'))
                        prev_r = r
            except Exception:
                pass
            time.sleep(0.005)

    # ── Analysis ─────────────────────────────────────────────────────────────

    def run_instant_checks(self) -> list:
        """
        Perform checks that must run IMMEDIATELY when the scanner starts
        (before the player has time to remove the weight or reconnect the mouse).
        Returns list of finding dicts.
        """
        findings = []

        # ── Check 1: any button physically held RIGHT NOW ────────────────────
        states = self._get_button_states()
        # Re-read 3 times spaced 100ms to reduce transient false positives
        all_states = [states]
        for _ in range(2):
            time.sleep(0.1)
            all_states.append(self._get_button_states())

        # A button must appear pressed in at least 2 of 3 samples
        held = []
        for btn in ('left', 'right', 'middle'):
            pressed_count = sum(1 for s in all_states if s.get(btn))
            if pressed_count >= 2:
                held.append(btn)

        if held:
            labels = {'left': 'izquierdo', 'right': 'derecho', 'middle': 'central'}
            names  = [labels.get(b, b) for b in held]
            findings.append({
                'tipo':        'MOUSE_BUTTON_HELD_AT_START',
                'nombre':      f'Botón {" y ".join(names)} sostenido al iniciar el scanner',
                'ruta':        '',
                'detalle':     f'Confirmado en 3 lecturas separadas por 100ms. Botones: {", ".join(held)}',
                'alerta':      'CRITICAL',
                'categoria':   'MOUSE_WEIGHT',
                'descripcion': (
                    'Un botón del mouse estaba físicamente presionado en el instante '
                    'en que se inició el scanner (confirmado 2/3 lecturas). '
                    'Indica peso colocado sobre el botón (técnica estándar del click-bug en prison mode).'
                ),
            })

        # ── Check 2: mouse recently connected (registry timestamps) ─────────
        now_utc = datetime.utcnow()
        for dev in self.initial_devices:
            lw = dev.get('last_write')
            if lw is None:
                continue
            # last_write is already UTC-naive
            delta_min = (now_utc - lw).total_seconds() / 60
            if 0 <= delta_min < SUSPICION_RECENT_MINUTES:
                severity = 'CRITICAL' if delta_min < 5 else 'SOSPECHOSO'
                findings.append({
                    'tipo':        'MOUSE_RECENTLY_CONNECTED',
                    'nombre':      f'Mouse "{dev["friendly"]}" conectado hace {int(delta_min)} min',
                    'ruta':        '',
                    'detalle':     (
                        f'Último registro: {lw.strftime("%H:%M:%S")} UTC '
                        f'— {int(delta_min)} minuto(s) antes del escaneo'
                    ),
                    'alerta':      severity,
                    'categoria':   'MOUSE_WEIGHT',
                    'descripcion': (
                        f'El mouse "{dev["friendly"]}" fue conectado hace solo {int(delta_min)} min. '
                        'En prison SS via AnyDesk, el jugador puede desconectar el mouse mientras '
                        'mantiene el click-bug activo y reconectarlo justo al recibir la petición de SS.'
                    ),
                })

        # ── Historical evidence (surviving artifacts from before SS) ────────
        # Run in a background thread so it doesn't slow down the instant check
        def _run_historical():
            hist = self.scan_historical_evidence()
            with self._lock:
                self._historical_findings.extend(hist)
            if hist:
                print(f"[MouseWeight] 🕵️  Evidencia histórica: {len(hist)} hallazgo(s)")

        self._historical_findings = []
        _t = threading.Thread(target=_run_historical, daemon=True,
                              name="MouseWeight-Historical")
        _t.start()
        _t.join(timeout=20)   # wait up to 20s (PowerShell query)

        with self._lock:
            findings.extend(self._historical_findings)

        return findings

    def get_session_findings(self) -> list:
        """
        Return all findings accumulated during background monitoring.
        Call this at the END of the scan to get plug/unplug events and click analysis.
        """
        findings = []

        # ── Device plug/unplug events ────────────────────────────────────────
        with self._lock:
            events = list(self.device_events)

        for evt in events:
            action = 'conectado' if evt['event'] == 'CONNECTED' else 'desconectado'
            ts_str = evt['ts'].strftime('%H:%M:%S')
            findings.append({
                'tipo':        f'MOUSE_{evt["event"]}_DURING_SS',
                'nombre':      f'Mouse {action} a las {ts_str} (durante el escaneo)',
                'ruta':        '',
                'detalle':     f'Dispositivo: {evt.get("friendly", evt["instance"])} — {ts_str}',
                'alerta':      'CRITICAL',
                'categoria':   'MOUSE_WEIGHT',
                'descripcion': (
                    f'Un dispositivo de mouse fue {action} mientras el scanner estaba activo ({ts_str}). '
                    'Indica que el jugador desconectó/reconectó el mouse para eliminar evidencia '
                    'del click-bug o retirar el peso durante la sesión.'
                ),
            })

        # ── Click pattern analysis ───────────────────────────────────────────
        findings.extend(self._analyze_click_patterns())

        return findings

    def _analyze_click_patterns(self) -> list:
        """Analyze recorded click events for mechanical regularity."""
        findings = []
        with self._lock:
            log = list(self.click_log)

        if not log:
            return findings

        for button, btn_label in (('L', 'izquierdo'), ('R', 'derecho')):
            btn_log = [(t, ev) for t, ev, b in log if b == button]
            if not btn_log:
                continue

            # ── Max held duration ────────────────────────────────────────────
            held_start  = None
            max_held    = 0.0
            for t, ev in btn_log:
                if ev == 'press':
                    held_start = t
                elif ev == 'release' and held_start is not None:
                    max_held   = max(max_held, t - held_start)
                    held_start = None
            if held_start is not None:
                max_held = max(max_held, time.perf_counter() - held_start)

            if max_held > 1.5:
                findings.append({
                    'tipo':        'MOUSE_BUTTON_HELD_LONG',
                    'nombre':      f'Botón {btn_label} sostenido {max_held:.1f}s',
                    'ruta':        '',
                    'detalle':     f'Pulsación máxima registrada: {max_held:.2f} segundos',
                    'alerta':      'CRITICAL',
                    'categoria':   'MOUSE_WEIGHT',
                    'descripcion': (
                        f'El botón {btn_label} se mantuvo presionado {max_held:.1f}s. '
                        'Un dedo humano no sostiene involuntariamente el botón >1.5s. '
                        'Indica peso físico sobre el botón o click-bug activo.'
                    ),
                })

            # ── Mechanical regularity ────────────────────────────────────────
            press_times = [t for t, ev in btn_log if ev == 'press']
            if len(press_times) >= 8:
                intervals = [press_times[k+1] - press_times[k]
                             for k in range(len(press_times) - 1)]
                mean_iv = sum(intervals) / len(intervals)
                variance = sum((x - mean_iv)**2 for x in intervals) / len(intervals)
                std_iv  = variance ** 0.5
                cps     = 1.0 / mean_iv if mean_iv > 0 else 0

                # Human variance is typically 30-200ms; mechanical < 15ms
                if cps > 7 and std_iv < 0.015:
                    severity = 'CRITICAL' if std_iv < 0.008 else 'SOSPECHOSO'
                    findings.append({
                        'tipo':        'MOUSE_MECHANICAL_CLICK_PATTERN',
                        'nombre':      (
                            f'Patrón mecánico en botón {btn_label}: '
                            f'{cps:.1f} CPS, σ={std_iv*1000:.1f}ms'
                        ),
                        'ruta':        '',
                        'detalle':     (
                            f'Muestras: {len(press_times)}  |  CPS: {cps:.1f}  |  '
                            f'Intervalo medio: {mean_iv*1000:.1f}ms  |  '
                            f'Desviación estándar: {std_iv*1000:.2f}ms'
                        ),
                        'alerta':      severity,
                        'categoria':   'MOUSE_WEIGHT',
                        'descripcion': (
                            f'Se detectaron {len(press_times)} clicks con regularidad inhumana '
                            f'en botón {btn_label} (CPS={cps:.1f}, σ={std_iv*1000:.2f}ms). '
                            'Un humano tiene >30ms de varianza. Esta regularidad es característica '
                            'de peso mecánico, jitter-click por motor, o autoclicker activo.'
                        ),
                    })

        return findings

    # ── Historical evidence (pre-SS) ─────────────────────────────────────────

    def scan_historical_evidence(self) -> list:
        """
        Look for evidence of mouse manipulation BEFORE the SS session started.
        These checks use persistent system artifacts that survive scanner deletion:

          1. setupapi.dev.log   — every HID connect/disconnect with timestamp
          2. Windows Event Log  — Kernel-PnP device arrival/removal (days of history)
          3. Prefetch files     — deleted autoclick tools leave .pf entries
          4. BAM registry       — last run time of ALL executables, even deleted ones

        Call this at scan start.
        """
        findings = []
        for method in (
            self._parse_setupapi_log,
            self._query_pnp_events,
            self._check_prefetch_autoclick,
            self._check_registry_history,
        ):
            try:
                findings.extend(method())
            except Exception as e:
                print(f"[MouseWeight] {method.__name__} error: {e}")
        return findings

    # ── Source 1: setupapi.dev.log ────────────────────────────────────────────

    def _parse_setupapi_log(self) -> list:
        """
        Parse C:\\Windows\\inf\\setupapi.dev.log for HID mouse device events.
        Every device connect/reconnect is logged here with exact timestamp.
        The file is a protected system log — players cannot delete it.

        Flags:
        - Any mouse connected in the last 6 hours
        - Repeated connect/disconnect pattern (click-bug activation technique)
        """
        import re, os
        log_path = r'C:\Windows\inf\setupapi.dev.log'
        if not os.path.exists(log_path):
            return []

        findings = []
        ts_re    = re.compile(r'^\[(\d{4}/\d{2}/\d{2} \d{2}:\d{2}:\d{2})')
        mouse_re = re.compile(r'mouse', re.IGNORECASE)
        hid_re   = re.compile(r'HID\\VID_[0-9A-Fa-f]{4}&PID_[0-9A-Fa-f]{4}', re.IGNORECASE)

        now      = datetime.utcnow()
        lookback = timedelta(hours=24)

        # Read only the last 200 KB (recent events are at the end)
        try:
            with open(log_path, 'r', encoding='utf-8', errors='replace') as f:
                f.seek(0, 2)
                size = f.tell()
                f.seek(max(0, size - 200_000))
                content = f.read()
        except PermissionError:
            return []

        blocks = re.split(r'\n(?=\[)', content)
        device_events: dict = {}   # device_id → list of datetimes

        for block in blocks:
            lines = block.strip().splitlines()
            if not lines:
                continue
            m = ts_re.match(lines[0])
            if not m:
                continue
            try:
                ts = datetime.strptime(m.group(1), '%Y/%m/%d %H:%M:%S')
            except ValueError:
                continue
            if now - ts > lookback:
                continue

            block_text = '\n'.join(lines)
            hid_match  = hid_re.search(block_text)
            is_mouse   = mouse_re.search(block_text)
            if not (is_mouse or hid_match):
                continue

            device_id = hid_match.group(0) if hid_match else 'HID_MOUSE'
            device_events.setdefault(device_id, []).append(ts)

        for device_id, timestamps in device_events.items():
            timestamps.sort()
            count     = len(timestamps)
            first     = timestamps[0]
            last      = timestamps[-1]
            delta_min = (now - last).total_seconds() / 60
            span_min  = (last - first).total_seconds() / 60

            if count >= 3:
                findings.append({
                    'tipo':        'MOUSE_REPEATED_RECONNECT_HISTORY',
                    'nombre':      f'setupapi.log: mouse reconectado {count}x en {int(span_min)} min',
                    'ruta':        log_path,
                    'detalle':     (
                        f'Dispositivo: {device_id} — '
                        f'{count} eventos entre {first.strftime("%H:%M")} y {last.strftime("%H:%M")} UTC'
                    ),
                    'alerta':      'CRITICAL' if count >= 5 else 'SOSPECHOSO',
                    'categoria':   'MOUSE_WEIGHT',
                    'descripcion': (
                        f'setupapi.dev.log registra {count} reconexiones del mouse en {int(span_min)} min. '
                        'Reconectar el mouse repetidamente es la técnica estándar para activar '
                        'y desactivar el click-bug en prison. Este log es un archivo de sistema '
                        'y NO puede ser borrado por el jugador.'
                    ),
                })
            elif count >= 1 and delta_min < 30:
                findings.append({
                    'tipo':        'MOUSE_RECENT_CONNECT_SETUPAPI',
                    'nombre':      f'setupapi.log: mouse conectado hace {int(delta_min)} min',
                    'ruta':        log_path,
                    'detalle':     f'Dispositivo: {device_id} — {last.strftime("%H:%M:%S")} UTC',
                    'alerta':      'CRITICAL' if delta_min < 5 else 'SOSPECHOSO',
                    'categoria':   'MOUSE_WEIGHT',
                    'descripcion': (
                        f'setupapi.dev.log confirma conexión de mouse hace {int(delta_min)} min. '
                        'Este es un log de sistema que el jugador no puede borrar. '
                        'La conexión reciente antes de la SS es indicativa de reconexión '
                        'para ocultar el click-bug.'
                    ),
                })

        return findings

    # ── Source 2: Windows Event Log (Kernel-PnP) ─────────────────────────────

    def _query_pnp_events(self) -> list:
        """
        Query the Windows System Event Log for Kernel-PnP device events via PowerShell.
          EventID 6416 — new external device recognized
          EventID 6419/6420 — device disabled/removed

        The Event Log is NOT deletable by regular users and persists for weeks.
        """
        import subprocess, re
        findings = []
        now = datetime.now()

        ps_cmd = (
            "Get-WinEvent -LogName System -MaxEvents 500 -ErrorAction SilentlyContinue "
            "| Where-Object {$_.Id -in @(6416,6419,6420)} "
            "| Select-Object -First 100 TimeCreated,Id,Message "
            "| ForEach-Object {"
            "  $_.TimeCreated.ToString('yyyy-MM-dd HH:mm:ss') + '|' + $_.Id + '|' + "
            "  ($_.Message -replace '\\s+', ' ')"
            "} | Out-String"
        )
        try:
            result = subprocess.run(
                ['powershell', '-NonInteractive', '-NoProfile', '-Command', ps_cmd],
                capture_output=True, text=True, timeout=15
            )
            output = result.stdout.strip()
        except (subprocess.TimeoutExpired, FileNotFoundError, OSError):
            return []

        if not output:
            return []

        ts_re    = re.compile(r'^(\d{4}-\d{2}-\d{2} \d{2}:\d{2}:\d{2})\|(\d+)\|(.*)')
        mouse_re = re.compile(r'mouse|HID', re.IGNORECASE)
        device_events = []

        for line in output.splitlines():
            m = ts_re.match(line.strip())
            if not m:
                continue
            try:
                ts  = datetime.strptime(m.group(1), '%Y-%m-%d %H:%M:%S')
                eid = int(m.group(2))
                msg = m.group(3)
            except (ValueError, IndexError):
                continue
            delta_h = (now - ts).total_seconds() / 3600
            if delta_h > 24:
                continue
            if mouse_re.search(msg):
                device_events.append((ts, eid, msg[:120]))

        recent_1h = [(ts, eid, msg) for ts, eid, msg in device_events
                     if (now - ts).total_seconds() < 3600 and eid == 6416]

        for ts, eid, msg in recent_1h:
            delta_min = (now - ts).total_seconds() / 60
            findings.append({
                'tipo':        'MOUSE_EVENTLOG_CONNECT',
                'nombre':      f'Event Log (ID {eid}): dispositivo HID hace {int(delta_min)} min',
                'ruta':        'System Event Log (Kernel-PnP)',
                'detalle':     f'{ts.strftime("%H:%M:%S")} — {msg[:80]}',
                'alerta':      'CRITICAL' if delta_min < 10 else 'SOSPECHOSO',
                'categoria':   'MOUSE_WEIGHT',
                'descripcion': (
                    f'El Event Log del sistema (EventID {eid}) registró la conexión de un '
                    f'dispositivo HID hace {int(delta_min)} min. '
                    'Este log no puede ser borrado por el jugador. '
                    'Una conexión de mouse justo antes de la SS es altamente sospechosa.'
                ),
            })

        if len(device_events) >= 5:
            findings.append({
                'tipo':        'MOUSE_EVENTLOG_REPEATED',
                'nombre':      f'Event Log: {len(device_events)} eventos HID en 24h',
                'ruta':        'System Event Log',
                'detalle':     f'{len(device_events)} eventos Kernel-PnP (IDs 6416/6419/6420) en 24h',
                'alerta':      'SOSPECHOSO',
                'categoria':   'MOUSE_WEIGHT',
                'descripcion': (
                    f'{len(device_events)} eventos de conexión/desconexión de dispositivo en 24h. '
                    'Frecuencia elevada puede indicar desconexiones repetidas del mouse '
                    'para activar/desactivar el click-bug.'
                ),
            })

        return findings

    # ── Source 3: Prefetch for deleted autoclick tools ────────────────────────

    def _check_prefetch_autoclick(self) -> list:
        """
        Scan C:\\Windows\\Prefetch\\ for autoclick/jitter tool names.
        Windows creates a .pf file the FIRST TIME any executable runs.
        The .pf file SURVIVES even if the player deletes the tool.
        This is one of the strongest forensic artifacts available.
        """
        import os
        findings = []
        prefetch_dir = r'C:\Windows\Prefetch'
        if not os.path.exists(prefetch_dir):
            return []

        PATTERNS = [
            'autoclick', 'auto_click', 'autoclicker', 'auto-click',
            'jitter', 'jitterclick', 'jitter_click', 'jitter-click',
            'weightclick', 'weight_click', 'clickbot', 'click_bot',
            'ghostmouse', 'ghost_mouse', 'mouseghost', 'mouserecorder',
            'cpstool', 'cps_tool', 'cpsmeter', 'cpstest',
            'tinyclick', 'rapidclick', 'fastclick', 'macroclick',
            'ahk', 'autohotkey', 'pyautogui',
        ]

        now = datetime.now()
        try:
            entries = os.listdir(prefetch_dir)
        except PermissionError:
            return []

        for fname in entries:
            if not fname.upper().endswith('.PF'):
                continue
            lower = fname.lower()
            matched = next((p for p in PATTERNS if p in lower), None)
            if not matched:
                continue

            pf_path = os.path.join(prefetch_dir, fname)
            try:
                mtime   = os.path.getmtime(pf_path)
                last_dt = datetime.fromtimestamp(mtime)
                delta_h = (now - last_dt).total_seconds() / 3600
            except OSError:
                last_dt, delta_h = None, 999

            exe_name = fname.split('-')[0] if '-' in fname else fname.replace('.PF', '')
            severity = ('CRITICAL' if delta_h < 2
                        else 'SOSPECHOSO' if delta_h < 24
                        else 'POCO_SOSPECHOSO')

            findings.append({
                'tipo':        'MOUSE_AUTOCLICK_PREFETCH',
                'nombre':      f'Prefetch: "{exe_name}" ejecutado hace ~{int(delta_h)}h',
                'ruta':        pf_path,
                'detalle':     (
                    f'Archivo: {fname} — '
                    f'última ejecución: {last_dt.strftime("%Y-%m-%d %H:%M") if last_dt else "?"}'
                ),
                'alerta':      severity,
                'categoria':   'MOUSE_WEIGHT',
                'descripcion': (
                    f'Prefetch confirma que "{exe_name}" fue ejecutado hace ~{int(delta_h)}h. '
                    'Los archivos Prefetch persisten AUNQUE el exe sea eliminado. '
                    'El jugador no puede borrar este rastro sin permisos de sistema. '
                    f'Patrón detectado: "{matched}".'
                ),
            })

        return findings

    # ── Source 4: Extended registry + BAM ────────────────────────────────────

    def _check_registry_history(self) -> list:
        """
        1. HID registry timestamps with 6-hour window (complement to run_instant_checks).
        2. BAM (Background Activity Moderator) — records last execution time of ALL
           executables, INCLUDING those that were DELETED from disk.
           Path: HKLM\\SYSTEM\\CurrentControlSet\\Services\\bam\\State\\UserSettings\\{SID}
        """
        import struct, os
        findings = []
        now_utc  = datetime.utcnow()

        # ── 4a. HID extended window (20min–6h) ───────────────────────────────
        for dev in self.initial_devices:
            lw = dev.get('last_write')
            if lw is None:
                continue
            delta_h = (now_utc - lw).total_seconds() / 3600
            if 0.33 < delta_h <= 6:
                findings.append({
                    'tipo':        'MOUSE_REGISTRY_CONNECT_6H',
                    'nombre':      f'Registro HID: mouse conectado hace {delta_h:.1f}h',
                    'ruta':        f'HKLM\\SYSTEM\\CurrentControlSet\\Enum\\HID\\{dev["device_id"]}',
                    'detalle':     f'{dev["friendly"]} — last_write: {lw.strftime("%H:%M")} UTC',
                    'alerta':      'SOSPECHOSO',
                    'categoria':   'MOUSE_WEIGHT',
                    'descripcion': (
                        f'El registro HID muestra que "{dev["friendly"]}" fue conectado '
                        f'hace {delta_h:.1f}h. Puede ser consistente con haber usado '
                        'el click-bug y desconectado el mouse antes de la SS.'
                    ),
                })

        # ── 4b. BAM — Background Activity Moderator ──────────────────────────
        AUTOCLICK_BAM = [
            'autoclick', 'autoclicker', 'jitter', 'clickbot', 'ghostmouse',
            'macro', 'ahk', 'autohotkey', 'pyautogui', 'cpstool', 'tinyclick',
            'weightclick', 'rapidclick', 'mouserecorder',
        ]
        try:
            bam_base = r'SYSTEM\CurrentControlSet\Services\bam\State\UserSettings'
            with winreg.OpenKey(winreg.HKEY_LOCAL_MACHINE, bam_base) as bam_key:
                i = 0
                while True:
                    try:
                        sid_name = winreg.EnumKey(bam_key, i)
                    except OSError:
                        break
                    i += 1
                    try:
                        with winreg.OpenKey(bam_key, sid_name) as sid_key:
                            j = 0
                            while True:
                                try:
                                    val_name, val_data, _ = winreg.EnumValue(sid_key, j)
                                except OSError:
                                    break
                                j += 1
                                lower_name = val_name.lower()
                                matched = next(
                                    (p for p in AUTOCLICK_BAM if p in lower_name), None)
                                if not matched:
                                    continue
                                if not (isinstance(val_data, bytes) and len(val_data) >= 8):
                                    continue
                                ft = struct.unpack_from('<Q', val_data)[0]
                                if ft == 0:
                                    continue
                                last_run = _filetime_to_dt(ft)
                                delta_h  = (now_utc - last_run).total_seconds() / 3600
                                if delta_h > 168:
                                    continue
                                exe_short = val_name.split('\\')[-1] if '\\' in val_name else val_name
                                severity  = 'CRITICAL' if delta_h < 3 else 'SOSPECHOSO'
                                findings.append({
                                    'tipo':        'MOUSE_BAM_AUTOCLICK',
                                    'nombre':      f'BAM: "{exe_short}" ejecutado hace {delta_h:.1f}h',
                                    'ruta':        val_name,
                                    'detalle':     (
                                        f'Ruta: {val_name[:80]}\n'
                                        f'Última ejecución: {last_run.strftime("%Y-%m-%d %H:%M")} UTC '
                                        f'(hace {delta_h:.1f}h)'
                                    ),
                                    'alerta':      severity,
                                    'categoria':   'MOUSE_WEIGHT',
                                    'descripcion': (
                                        f'BAM Registry indica que "{exe_short}" se ejecutó hace {delta_h:.1f}h. '
                                        'BAM registra la última ejecución de TODO ejecutable, '
                                        'incluyendo los ya ELIMINADOS del disco. '
                                        'El jugador no puede borrar esta entrada sin herramientas forenses.'
                                    ),
                                })
                    except OSError:
                        continue
        except OSError:
            pass  # BAM not available on very old Windows

        return findings
