"""
Argus Scanner — UI enhancements (sección A) + Visual Pack B (80+ mejoras).
Se integra con ModernUI vía patch_modern_ui().
"""
from __future__ import annotations

import json
import os
import sys
import threading
import webbrowser
import tkinter as tk
from tkinter import messagebox

try:
    import urllib.request
except ImportError:
    urllib = None  # type: ignore


def _base_path():
    if getattr(sys, 'frozen', False):
        return sys._MEIPASS
    return os.path.dirname(os.path.abspath(__file__))


def load_ui_prefs():
    """Lee preferencias UI desde config.json junto al exe o en source/."""
    defaults = {
        'ui_compact': False,
        'ui_high_contrast': False,
        'ui_reduced_motion': False,
        'ui_sound_on_complete': False,
        'web_url': 'https://asperss.onrender.com',
    }
    paths = [
        os.path.join(_base_path(), 'config.json'),
        os.path.join(os.path.dirname(_base_path()), 'config.json'),
    ]
    for p in paths:
        try:
            if os.path.isfile(p):
                with open(p, 'r', encoding='utf-8') as f:
                    data = json.load(f)
                ui = data.get('ui') or {}
                mapping = {
                    'ui_compact': ui.get('compact', defaults['ui_compact']),
                    'ui_high_contrast': ui.get('high_contrast', defaults['ui_high_contrast']),
                    'ui_reduced_motion': ui.get('reduced_motion', defaults['ui_reduced_motion']),
                    'ui_sound_on_complete': ui.get('sound_on_complete', defaults['ui_sound_on_complete']),
                }
                defaults.update(mapping)
                if 'web_url' in data:
                    defaults['web_url'] = data['web_url']
                break
        except Exception:
            pass
    return defaults


def patch_modern_ui(cls):
    """Añade métodos de mejora a la clase ModernUI."""
    prefs = load_ui_prefs()
    if os.environ.get('ARGUS_LITE') == '1':
        prefs['ui_reduced_motion'] = True
        prefs['ui_compact'] = True
    cls._ui_prefs = prefs
    cls._phase_history = []
    cls._risk_history = []
    cls._files_scanned = 0
    cls._network_ok = True
    cls._update_available = None
    cls._sparkline_canvas = None
    cls._upload_status_label = None
    cls._copy_btn = None
    cls._files_count_label = None
    cls._net_indicator = None
    cls._token_indicator = None
    cls._phase_list_frame = None
    cls._expanded_mode = not prefs.get('ui_compact', False)
    cls._cancel_confirm_pending = False

    @classmethod
    def apply_ui_prefs(cls, root):
        if prefs.get('ui_high_contrast'):
            cls.COLORS.update({
                'bg_primary': '#000000',
                'bg_card': '#111111',
                'text_primary': '#FFFFFF',
                'text_secondary': '#CCCCCC',
                'accent': '#FFFFFF',
                'accent_light': '#FFFFFF',
            })
        if prefs.get('ui_reduced_motion'):
            cls._stop_ambient_motion()
            cls._stop_badge_pulse()

    @classmethod
    def toggle_expanded_mode(cls, root):
        cls._expanded_mode = not cls._expanded_mode
        w, h = (880, 420) if cls._expanded_mode else (705, 279)
        x = (root.winfo_screenwidth() - w) // 2
        y = (root.winfo_screenheight() - h) // 2
        root.geometry(f'{w}x{h}+{x}+{y}')
        if cls._phase_list_frame:
            if cls._expanded_mode:
                cls._phase_list_frame.pack(fill=tk.X, padx=24, pady=(0, 6))
            else:
                cls._phase_list_frame.pack_forget()

    @classmethod
    def show_splash(cls, root, version: str, on_done=None):
        C = cls.COLORS
        splash = tk.Toplevel(root)
        splash.overrideredirect(True)
        sw, sh = 320, 160
        x = (splash.winfo_screenwidth() - sw) // 2
        y = (splash.winfo_screenheight() - sh) // 2
        splash.geometry(f'{sw}x{sh}+{x}+{y}')
        splash.configure(bg=C['bg_primary'])
        splash.attributes('-topmost', True)
        try:
            splash.attributes('-alpha', 0.0)
        except Exception:
            pass
        try:
            from ui_style import create_wordmark_label
            create_wordmark_label(splash, height=36, pady=(24, 8))
        except Exception:
            tk.Label(splash, text='ARGUS', font=('Segoe UI', 14, 'bold'),
                     bg=C['bg_primary'], fg=C['accent_light']).pack(pady=(28, 4))
        tk.Label(splash, text=f'v{version}', font=('Consolas', 9),
                 bg=C['bg_primary'], fg=C['text_secondary']).pack()

        def _fade_in(step=0):
            try:
                splash.attributes('-alpha', min(1.0, step / 8.0))
                if step < 8:
                    splash.after(30, lambda: _fade_in(step + 1))
            except Exception:
                pass

        def _close():
            try:
                splash.destroy()
            except Exception:
                pass
            if on_done:
                on_done()

        splash.after(80, _fade_in)
        splash.after(1500, _close)

    @classmethod
    def fade_out_and_quit(cls, root):
        try:
            def _step(a=1.0):
                a -= 0.08
                if a <= 0:
                    root.destroy()
                    return
                root.attributes('-alpha', max(0, a))
                root.after(25, lambda: _step(a))
            _step()
        except Exception:
            root.destroy()

    @classmethod
    def enhance_header(cls, hdr, inner, right=None):
        C = cls.COLORS
        parent = right or inner
        # Red / Sin red
        net = tk.Label(parent, text='Online', font=('Segoe UI', 7),
                       bg=C['bg_primary'], fg=C['green'])
        net.pack(side=tk.RIGHT, padx=(0, 8))
        cls._net_indicator = net

        # Token indicator
        tok = tk.Label(parent, text='Token', font=('Segoe UI', 7),
                       bg=C['bg_primary'], fg=C['text_muted'])
        tok.pack(side=tk.RIGHT, padx=(0, 6))
        cls._token_indicator = tok

        # Toggle expandido
        tg = tk.Label(parent, text='⤢', font=('Segoe UI', 9),
                      bg=C['bg_primary'], fg=C['text_muted'], cursor='hand2')
        tg.pack(side=tk.RIGHT, padx=(0, 6))
        if cls._root_ref:
            tg.bind('<Button-1>', lambda _e: cls.toggle_expanded_mode(cls._root_ref))

        # Versión clickeable → changelog (duplicado opcional si header ya tiene ver)
        if cls._app_version and not right:
            vl = tk.Label(parent, text=f'v{cls._app_version}', font=('Consolas', 7),
                          bg=C['bg_primary'], fg=C['text_muted'], cursor='hand2')
            vl.pack(side=tk.RIGHT, padx=(0, 8))
            base = prefs.get('web_url', 'https://asperss.onrender.com').rstrip('/')
            vl.bind('<Button-1>', lambda _e: webbrowser.open(f'{base}/descargar'))

    @classmethod
    def set_network_status(cls, online: bool):
        cls._network_ok = bool(online)
        if cls._net_indicator:
            if online:
                cls._net_indicator.config(text='Online', fg=cls.COLORS['green'])
            else:
                cls._net_indicator.config(text='Sin red', fg=cls.COLORS['red'])

    @classmethod
    def set_token_status(cls, valid: bool | None):
        if not cls._token_indicator:
            return
        if valid is True:
            cls._token_indicator.config(text='Token OK', fg=cls.COLORS['green'])
        elif valid is False:
            cls._token_indicator.config(text='Token err', fg=cls.COLORS['red'])
        else:
            cls._token_indicator.config(text='Token', fg=cls.COLORS['text_muted'])

    @classmethod
    def append_phase_history(cls, text: str):
        if not text:
            return
        try:
            from ui_style import sanitize_ui_text
            text = sanitize_ui_text(text)
        except Exception:
            pass
        cls._phase_history.append(text)
        cls._phase_history = cls._phase_history[-5:]
        if cls._phase_list_frame:
            for w in cls._phase_list_frame.winfo_children():
                w.destroy()
            C = cls.COLORS
            try:
                from ui_style import sanitize_ui_text as _san
            except Exception:
                _san = lambda x: x
            for line in cls._phase_history:
                tk.Label(cls._phase_list_frame, text=_san(line)[:60],
                         font=('Consolas', 7), bg=C['bg_primary'],
                         fg=C['text_muted'], anchor='w').pack(fill=tk.X)

    @classmethod
    def create_phase_sidebar(cls, parent):
        C = cls.COLORS
        fr = tk.Frame(parent, bg=C['bg_primary'])
        cls._phase_list_frame = fr
        if cls._expanded_mode:
            fr.pack(fill=tk.X, padx=24, pady=(0, 6))
        return fr

    @classmethod
    def create_sparkline(cls, parent):
        C = cls.COLORS
        bg = C.get('bg_primary', '#09090b')
        c = tk.Canvas(parent, width=80, height=24, bg=bg, highlightthickness=0)
        c.place(relx=1.0, rely=0.0, anchor='ne', x=-12, y=52)
        cls._sparkline_canvas = c
        return c

    @classmethod
    def push_risk_sample(cls, value: float):
        cls._risk_history.append(max(0, min(100, float(value))))
        cls._risk_history = cls._risk_history[-24:]
        c = cls._sparkline_canvas
        if not c:
            return
        try:
            c.delete('all')
            hist = cls._risk_history
            if len(hist) < 2:
                return
            w, h = 80, 24
            mx = max(hist) or 1
            pts = []
            for i, v in enumerate(hist):
                x = i * (w / max(len(hist) - 1, 1))
                y = h - (v / mx) * (h - 4) - 2
                pts.extend([x, y])
            col = cls.COLORS['red'] if hist[-1] > 70 else cls.COLORS['accent']
            c.create_line(*pts, fill=col, width=1.5, smooth=True)
        except Exception:
            pass

    @classmethod
    def set_files_scanned(cls, n: int):
        cls._files_scanned = int(n)
        if cls._files_count_label:
            cls._files_count_label.config(
                text=f'{cls._files_scanned:,} archivos'.replace(',', '.'))

    @classmethod
    def attach_files_counter(cls, parent):
        """Contador de archivos; si hay barra superior de progreso, no duplicar."""
        if getattr(cls, '_files_count_label', None):
            try:
                if cls._files_count_label.winfo_exists():
                    return cls._files_count_label
            except Exception:
                pass
        C = cls.COLORS
        top = getattr(cls, '_progress_top_bar', None)
        if top is not None:
            try:
                if top.winfo_exists():
                    return cls._files_count_label
            except Exception:
                pass
        bg = C.get('bg_secondary', C.get('bg_primary', '#04030e'))
        lbl = tk.Label(parent, text='0 archivos', font=('Consolas', 8),
                       bg=bg, fg=C['text_muted'])
        lbl.place(relx=1.0, rely=0.0, anchor='ne', x=-14, y=10)
        cls._files_count_label = lbl
        return lbl

    @classmethod
    def enhance_completion_panel(cls, widgets: dict):
        C = cls.COLORS
        center = widgets.get('card')
        if not center:
            return
        row = tk.Frame(center, bg=C['bg_card'])
        row.pack(pady=(10, 0))

        def _copy():
            txt = []
            ml = widgets.get('main_label')
            sl = widgets.get('sub_label')
            tf = widgets.get('top_finding')
            if ml:
                txt.append(ml.cget('text'))
            if sl:
                txt.append(sl.cget('text'))
            if tf and tf.cget('text'):
                txt.append(tf.cget('text'))
            body = '\n'.join(txt)
            r = cls._root_ref
            if r:
                r.clipboard_clear()
                r.clipboard_append(body)
                r.update()

        btn = tk.Button(row, text='Copiar resumen', font=('Segoe UI', 8),
                        bg=C['bg_hover'], fg=C['accent_light'],
                        relief=tk.FLAT, cursor='hand2', command=_copy)
        btn.pack(side=tk.LEFT, padx=4)
        cls._copy_btn = btn

        up = tk.Label(row, text='', font=('Segoe UI', 8),
                      bg=C['bg_card'], fg=C['text_muted'])
        up.pack(side=tk.LEFT, padx=8)
        cls._upload_status_label = up

    @classmethod
    def set_upload_status(cls, state: str, detail: str = ''):
        """state: pending | ok | error"""
        lbl = cls._upload_status_label
        if not lbl:
            return
        C = cls.COLORS
        if state == 'pending':
            lbl.config(text='Enviando al panel…', fg=C['amber'])
        elif state == 'ok':
            lbl.config(text='Enviado', fg=C['green'])
        elif state == 'error':
            lbl.config(text=f'Error{": " + detail if detail else ""}', fg=C['red'])
        else:
            lbl.config(text='', fg=C['text_muted'])

    @classmethod
    def wire_cancel_confirm(cls, cancel_btn, on_confirm):
        def _click():
            if not cls._cancel_confirm_pending:
                cls._cancel_confirm_pending = True
                cancel_btn.config(text='¿Seguro? Clic de nuevo', fg=cls.COLORS['red'])
                cancel_btn.after(2000, _reset)
                return
            cls._cancel_confirm_pending = False
            on_confirm()

        def _reset():
            cls._cancel_confirm_pending = False
            try:
                cancel_btn.config(text='Cancelar escaneo', fg=cls.COLORS['text_muted'])
            except Exception:
                pass

        cancel_btn.config(command=_click)

    @classmethod
    def flash_dwm_border(cls, success: bool):
        root = cls._root_ref
        if not root:
            return
        try:
            import ctypes
            hwnd = ctypes.windll.user32.GetParent(root.winfo_id()) or root.winfo_id()
            color = 0x0037D399 if success else 0x002626DC  # BGR
            ctypes.windll.dwmapi.DwmSetWindowAttribute(
                hwnd, 34, ctypes.byref(ctypes.c_int(color)), ctypes.sizeof(ctypes.c_int))
            def _revert():
                border = ctypes.c_int(0x00FF7B8B)  # BGR #8b7bff
                ctypes.windll.dwmapi.DwmSetWindowAttribute(
                    hwnd, 34, ctypes.byref(border), ctypes.sizeof(border))
            root.after(800, _revert)
        except Exception:
            pass

    @classmethod
    def play_complete_sound(cls):
        if not prefs.get('ui_sound_on_complete'):
            return
        try:
            import winsound
            winsound.MessageBeep(winsound.MB_OK)
        except Exception:
            pass

    @classmethod
    def check_update_async(cls, api_base: str, current: str):
        def _run():
            try:
                url = f'{api_base.rstrip("/")}/api/version'
                if urllib:
                    with urllib.request.urlopen(url, timeout=6) as resp:
                        data = json.loads(resp.read().decode())
                else:
                    return
                remote = data.get('scanner_version') or data.get('version') or ''
                if remote and remote != current:
                    cls._update_available = remote
            except Exception:
                cls._network_ok = False

        threading.Thread(target=_run, daemon=True).start()

    @classmethod
    def show_auth_error_screen(cls, root, message: str):
        C = cls.COLORS
        win = tk.Toplevel(root)
        win.title('Error de autenticación')
        win.configure(bg=C['bg_primary'])
        win.geometry('400x220')
        win.resizable(False, False)
        try:
            from ui_style import create_wordmark_label
            create_wordmark_label(win, height=32, pady=(16, 8))
        except Exception:
            pass
        tk.Label(win, text='Autenticación fallida', font=('Segoe UI', 12, 'bold'),
                 bg=C['bg_primary'], fg=C['red_deep']).pack(pady=(8, 8))
        tk.Label(win, text=message[:200], wraplength=360, justify='center',
                 font=('Segoe UI', 9), bg=C['bg_primary'], fg=C['text_secondary']).pack(padx=20)
        tk.Button(win, text='Cerrar', command=lambda: (win.destroy(), root.destroy()),
                  bg=C['accent'], fg=C['bg_primary'], relief=tk.FLAT,
                  padx=20, pady=6).pack(pady=20)

    @classmethod
    def add_chip_tooltips(cls, chip_widgets: dict):
        tips = {
            'critical': 'CRIT: hallazgo de alta confianza — revisar de inmediato',
            'suspicious': 'SOSP: indicio que requiere investigación',
            'low': 'BAJO: señal débil o contextual',
            'clean': 'OK: sin alertas en esta categoría',
        }
        C = cls.COLORS
        for key, w in (chip_widgets or {}).items():
            tip = tips.get(key)
            if not tip or w is None:
                continue
            def _enter(e, t=tip, widget=w, _C=C):
                tw = tk.Toplevel(widget)
                tw.wm_overrideredirect(True)
                tw.configure(bg=_C['bg_card'])
                lbl = tk.Label(tw, text=t, font=('Segoe UI', 7),
                               bg=_C['bg_card'], fg=_C['text_secondary'],
                               padx=6, pady=3)
                lbl.pack()
                x = widget.winfo_rootx()
                y = widget.winfo_rooty() + widget.winfo_height() + 4
                tw.geometry(f'+{x}+{y}')
                widget._tip = tw

            def _leave(e, widget=w):
                tw = getattr(widget, '_tip', None)
                if tw:
                    tw.destroy()
                    widget._tip = None

            try:
                w.bind('<Enter>', _enter)
                w.bind('<Leave>', _leave)
            except Exception:
                pass

    @classmethod
    def setup_tray(cls, root, on_open=None, on_cancel=None, on_quit=None):
        try:
            import pystray
            from PIL import Image
        except ImportError:
            return None
        icon_path = os.path.join(_base_path(), 'assets', 'logo.png')
        img = Image.open(icon_path) if os.path.isfile(icon_path) else Image.new('RGB', (32, 32), '#B87333')

        def _open(_i, _it):
            if on_open:
                on_open()
            try:
                root.deiconify()
            except Exception:
                pass

        def _quit(_i, _it):
            if on_quit:
                on_quit()
            root.after(0, root.destroy)

        menu = pystray.Menu(
            pystray.MenuItem('Abrir', _open),
            pystray.MenuItem('Salir', _quit),
        )
        icon = pystray.Icon('argus', img, 'Argus Scanner', menu)

        def _run():
            icon.run()

        threading.Thread(target=_run, daemon=True).start()
        return icon

    _method_names = (
        'apply_ui_prefs', 'toggle_expanded_mode', 'show_splash', 'fade_out_and_quit',
        'enhance_header', 'set_network_status', 'set_token_status', 'append_phase_history',
        'create_phase_sidebar', 'create_sparkline', 'push_risk_sample', 'set_files_scanned',
        'attach_files_counter', 'enhance_completion_panel', 'set_upload_status',
        'wire_cancel_confirm', 'flash_dwm_border', 'play_complete_sound', 'check_update_async',
        'show_auth_error_screen', 'add_chip_tooltips', 'setup_tray',
    )
    for _name in _method_names:
        setattr(cls, _name, locals()[_name])

    try:
        from ui_visual_pack_b import patch_visual_pack_b
        cls._visual_pack_count = patch_visual_pack_b(cls)
    except Exception as _vb_err:
        cls._visual_pack_count = 0
        print(f'[ui] Visual Pack B no cargado: {_vb_err}')
