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
        self.start_dt          = datetime.now()
        self._monitoring       = False
        self._lock             = threading.Lock()
        self.device_events     = []   # list of {ts, event, instance, friendly}
        self.click_log         = []   # list of (perf_counter, 'press'|'release', 'L'|'R')

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
