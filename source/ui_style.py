"""
Argus Scanner — UI Style v5 (Minimal × Eye Hybrid)
===================================================
Dark cosmic base + violet/cyan accents + orbit progress animation.
Floating shields, clean typography, no heavy cards.

API pública (usada por main.py):
    apply_window_style, create_header, create_progress_section,
    create_completion_panel, create_button, create_results_section,
    set_status_badge, update_counter, update_canvas_bar,
    set_completion_state, COLORS, FONTS.
"""
import tkinter as tk
from tkinter import ttk, scrolledtext
import os, sys, math, random, ctypes, base64, io, re

try:
    from PIL import Image, ImageTk
    _PIL_OK = True
except ImportError:
    _PIL_OK = False

_SHIELD_B64 = None

def _load_shield_b64():
    global _SHIELD_B64
    if _SHIELD_B64 is not None:
        return _SHIELD_B64
    try:
        p = os.path.join(ModernUI._base_path(), 'assets', 'shield_b64.txt')
        if os.path.isfile(p):
            with open(p, 'r') as f:
                _SHIELD_B64 = f.read().strip()
    except Exception:
        pass
    return _SHIELD_B64


_EMOJI_UI_RE = re.compile(
    "["
    "\U0001F300-\U0001FAFF"
    "\U00002600-\U000027BF"
    "\U00002300-\U000024FF"
    "\U00002B50"
    "\U0000FE0F"
    "\U0000200D"
    "]+",
    flags=re.UNICODE,
)


def sanitize_ui_text(text):
    """Quita emojis/símbolos decorativos del texto mostrado en la UI."""
    if not text:
        return ""
    s = _EMOJI_UI_RE.sub("", str(text))
    return " ".join(s.split())


def _assets_dir():
    if getattr(sys, "frozen", False):
        return os.path.join(sys._MEIPASS, "assets")
    return os.path.join(os.path.dirname(os.path.abspath(__file__)), "assets")


def create_wordmark_label(parent, height=40, pady=(0, 12), pack_opts=None):
    """Logo cósmico ARGUS (assets/argus-wordmark.png). Sin emojis."""
    try:
        bg = parent.cget("bg")
    except Exception:
        bg = "#04030e"

    def _fallback_text():
        return tk.Label(
            parent, text="ARGUS",
            font=("Segoe UI", max(14, height // 3), "bold"),
            bg=bg, fg="#8b7bff",
        )

    def _do_pack(lbl):
        if pack_opts is False:
            return
        if isinstance(pack_opts, dict):
            lbl.pack(**pack_opts)
        else:
            lbl.pack(pady=pady)

    path = os.path.join(_assets_dir(), "argus-wordmark.png")
    if not _PIL_OK or not os.path.isfile(path):
        lbl = _fallback_text()
        _do_pack(lbl)
        return lbl
    try:
        img = Image.open(path).convert("RGBA")
        iw, ih = img.size
        nh = max(16, int(height))
        nw = max(40, int(iw * nh / max(ih, 1)))
        img = img.resize((nw, nh), Image.LANCZOS)
        photo = ImageTk.PhotoImage(img)
        lbl = tk.Label(parent, image=photo, bg=bg)
        lbl.image = photo
        _do_pack(lbl)
        return lbl
    except Exception:
        lbl = _fallback_text()
        _do_pack(lbl)
        return lbl


def create_shield_label(parent, size=56, pady=(0, 12), pack_opts=None):
    """Compat: usa el wordmark cósmico (height ~= size)."""
    return create_wordmark_label(parent, height=size, pady=pady, pack_opts=pack_opts)


class _CanvasTextProxy:
    """Texto en canvas (compatible con Label.config / cget de main.py)."""

    def __init__(self, canvas, item_id):
        self._canvas = canvas
        self._item_id = item_id

    @staticmethod
    def _clean_status(text):
        """El % vive en el sol; no repetir (12%) en la línea de estado."""
        t = sanitize_ui_text(str(text or ''))
        return re.sub(r'\s*\(\s*\d+\s*%\s*\)\s*$', '', t).strip() or t

    def config(self, **kw):
        if 'text' in kw:
            txt = str(kw['text'])
            if getattr(ModernUI, '_hud_status_proxy', None) is self:
                txt = self._clean_status(txt)
            self._canvas.itemconfig(self._item_id, text=txt)
        if 'fg' in kw:
            self._canvas.itemconfig(self._item_id, fill=kw['fg'])

    def cget(self, key):
        if key == 'text':
            return self._canvas.itemcget(self._item_id, 'text')
        if key == 'fg':
            return self._canvas.itemcget(self._item_id, 'fill')
        return ''


class _CanvasBarProxy:
    """Barra de progreso dibujada en el canvas de fondo."""

    def __init__(self, draw_fn):
        self._draw = draw_fn


class ModernUI:
    """Argus Scanner — UI cósmica (alineada con Argus Vault / web)."""

    # Color clave para “agujeros” sobre el fondo animado (Windows).
    UI_CHROMA = '#010102'
    SCAN_BG_ASSET = 'cosmic-scan-bg.gif'

    COLORS = {
        'bg_primary':     '#04030e',
        'bg_secondary':   '#0a0a1f',
        'bg_card':        '#12122a',
        'bg_hover':       '#1a1a3a',
        'bg_inset':       '#0d0d20',
        'text_primary':   '#ECEDFF',
        'text_secondary': '#A6A8D0',
        'text_muted':     '#7E81AD',
        'accent':         '#8b7bff',
        'accent_light':   '#46e6ff',
        'accent_hover':   '#a89bff',
        'accent_deep':    '#3d3580',
        'accent_glow':    '#46e6ff',
        'accent_muted':   '#1a1835',
        'accent_soft':    '#12122a',
        'success_soft':   '#0d2e28',
        'green':          '#34d399',
        'green_glow':     '#6ee7b7',
        'amber':          '#fbbf24',
        'red':            '#f4506e',
        'red_deep':       '#DC2626',
        'blue':           '#46e6ff',
        'gold':           '#c4b5fd',
        'border':         '#252340',
        'border_bright':  '#3d3580',
        'separator':      '#18182e',
    }

    FONTS = {
        'title':    ('Segoe UI', 11, 'bold'),
        'subtitle': ('Segoe UI', 8),
        'body':     ('Segoe UI', 10),
        'small':    ('Segoe UI', 8),
        'mono':     ('Consolas', 8),
        'label_sm': ('Segoe UI', 7, 'bold'),
        'phase':    ('Segoe UI', 10),
        'done':     ('Segoe UI', 13, 'bold'),
        'big_pct':  ('Segoe UI', 52, 'bold'),
    }

    _style_applied = False
    _status_badge = None
    _status_badge_canvas = None
    _ring_canvas = None
    _ring_after_id = None
    _particle_canvas = None
    _particles = []
    _particle_after_id = None
    _shimmer_canvas = None
    _shimmer_after_id = None
    _shimmer_offset = 0
    _app_version = ''
    _root_ref = None
    _quit_callback = None
    _phase_dots_canvas = None
    _risk_canvas = None
    _risk_label = None
    _cpu_bar_canvas = None
    _ram_bar_canvas = None
    _detail_label_ref = None
    _status_label_ref = None
    _detail_fade_gen = 0
    _scanning_active = False
    _top_finding_label = None
    _counter_prev = {}
    _ring_pct = 0.0
    _ring_target_pct = 0.0
    _pct_tween_after = None
    _ambient_phase = 0.0
    _badge_pulse_after = None
    _badge_pulse_state = 0
    _counter_labels = {}

    # floating shields
    _bg_canvas = None
    _shield_images = []
    _shield_items = []
    _bg_anim_id = None
    _section_bg_canvas = None
    _section_bg_image_id = None
    _section_bg_frames = None
    _section_bg_photos = None
    _section_bg_anim_id = None

    # sistema solar (dibujado sobre el fondo animado)
    _orbit_canvas = None
    _orbit_after_id = None
    _orbit_arc = None
    _orbit_pct_text = None
    _orbit_pct_sign = None
    _solar_planets = []
    _solar_cx = _solar_cy = _solar_r = 0
    _hud_status_id = None
    _hud_detail_id = None
    _hud_timer_id = None
    _hud_resources_id = None
    _hud_bar_y = 0
    _solar_layout_key = None
    _solar_reposition_after = None

    @classmethod
    def set_quit_callback(cls, callback):
        cls._quit_callback = callback

    @classmethod
    def set_app_version(cls, version: str):
        cls._app_version = version or ''

    @classmethod
    def set_scanning_active(cls, active: bool):
        cls._scanning_active = bool(active)
        if active:
            cls._start_solar_animation()
        else:
            cls._stop_solar_animation()

    @classmethod
    def _apply_ttk_style(cls):
        if cls._style_applied:
            return
        cls._style_applied = True
        s = ttk.Style()
        try:
            s.theme_use('clam')
        except Exception:
            pass
        s.configure(
            'Argus.Horizontal.TProgressbar',
            background=cls.COLORS['accent'],
            troughcolor=cls.COLORS['bg_secondary'],
            borderwidth=0,
            lightcolor=cls.COLORS['accent'],
            darkcolor=cls.COLORS['accent'],
            thickness=3,
        )

    @staticmethod
    def _base_path():
        if getattr(sys, 'frozen', False):
            return sys._MEIPASS
        return os.path.dirname(os.path.abspath(__file__))

    # ══════════════════════════════════════════════════════════════════════
    #  FLOATING SHIELD BACKGROUND
    # ══════════════════════════════════════════════════════════════════════
    @classmethod
    def _paint_nebula_on_canvas(cls, canvas, tag='nebula'):
        """Gradiente cósmico en un canvas (reutilizable en root y sección de escaneo)."""
        canvas.delete(tag)
        w = max(canvas.winfo_width(), 400)
        h = max(canvas.winfo_height(), 320)
        canvas.create_oval(
            -w * 0.2, -h * 0.15, w * 0.55, h * 0.45,
            fill='#15122a', outline='', tags=tag)
        canvas.create_oval(
            w * 0.35, -h * 0.1, w * 1.1, h * 0.42,
            fill='#1a1038', outline='', tags=tag)
        canvas.create_oval(
            w * 0.1, h * 0.45, w * 0.9, h * 1.05,
            fill='#0c1428', outline='', tags=tag)
        canvas.create_oval(
            w * 0.25, h * 0.2, w * 0.75, h * 0.55,
            fill='#121830', outline='', tags=tag)

    @classmethod
    def _create_floating_bg(cls, parent):
        """Fondo cósmico en la ventana raíz."""
        C = cls.COLORS
        canvas = tk.Canvas(parent, bg=C['bg_primary'], highlightthickness=0, bd=0)
        canvas.place(x=0, y=0, relwidth=1.0, relheight=1.0)
        cls._bg_canvas = canvas
        cls._shield_images = []
        cls._shield_items = []

        def _paint(_e=None):
            cls._paint_nebula_on_canvas(canvas)

        canvas.bind('<Configure>', _paint)
        canvas.after(100, _paint)
        return canvas

    @classmethod
    def _scan_bg_reduced_motion(cls) -> bool:
        try:
            return bool(getattr(cls, '_ui_prefs', {}).get('ui_reduced_motion'))
        except Exception:
            return False

    @classmethod
    def _load_scan_bg_frames(cls):
        if cls._section_bg_frames is not None:
            return cls._section_bg_frames
        cls._section_bg_frames = []
        if not _PIL_OK:
            return cls._section_bg_frames
        path = os.path.join(cls._base_path(), 'assets', cls.SCAN_BG_ASSET)
        if not os.path.isfile(path):
            return cls._section_bg_frames
        try:
            im = Image.open(path)
            photos = []
            idx = 0
            while True:
                try:
                    im.seek(idx)
                except EOFError:
                    break
                photos.append(ImageTk.PhotoImage(im.copy().convert('RGB')))
                idx += 1
            cls._section_bg_frames = photos
            cls._section_bg_photos = photos
        except Exception:
            cls._section_bg_frames = []
        return cls._section_bg_frames

    @classmethod
    def _stop_section_bg_anim(cls):
        if cls._section_bg_anim_id and cls._root_ref:
            try:
                cls._root_ref.after_cancel(cls._section_bg_anim_id)
            except Exception:
                pass
        cls._section_bg_anim_id = None

    @classmethod
    def _start_section_bg_anim(cls, canvas, image_id):
        frames = cls._load_scan_bg_frames()
        if len(frames) < 2 or cls._scan_bg_reduced_motion():
            return

        def _tick(idx=0):
            try:
                if not canvas.winfo_exists():
                    return
                canvas.itemconfig(image_id, image=frames[idx % len(frames)])
                cls._raise_scan_layers(canvas)
                cls._section_bg_anim_id = canvas.after(85, lambda: _tick((idx + 1) % len(frames)))
            except Exception:
                pass

        cls._stop_section_bg_anim()
        _tick(0)

    @classmethod
    def _raise_scan_layers(cls, canvas):
        try:
            canvas.tag_lower('scan_bg')
            for tag in ('hud_bar', 'solar', 'hud'):
                canvas.tag_raise(tag)
        except Exception:
            pass

    @classmethod
    def _create_section_bg(cls, parent):
        """Fondo animado (GIF) o nebulosa estática de respaldo."""
        C = cls.COLORS
        canvas = tk.Canvas(parent, bg=C['bg_primary'], highlightthickness=0, bd=0)
        canvas.place(x=0, y=0, relwidth=1.0, relheight=1.0)
        cls._section_bg_canvas = canvas
        frames = cls._load_scan_bg_frames()

        if frames:
            def _place_img(_e=None):
                canvas.delete('scan_bg')
                cw = max(canvas.winfo_width(), 620)
                ch = max(canvas.winfo_height(), 440)
                cls._section_bg_image_id = canvas.create_image(
                    cw // 2, ch // 2, image=frames[0], tags='scan_bg')
                cls._raise_scan_layers(canvas)
                cls._start_section_bg_anim(canvas, cls._section_bg_image_id)

            canvas.bind('<Configure>', _place_img)
            parent.after(80, _place_img)
            return canvas

        def _paint(_e=None):
            cls._paint_nebula_on_canvas(canvas)

        canvas.bind('<Configure>', _paint)
        parent.after(50, _paint)
        return canvas

    # ══════════════════════════════════════════════════════════════════════
    #  WINDOW
    # ══════════════════════════════════════════════════════════════════════
    @staticmethod
    def apply_window_style(root):
        root.title("Argus Scanner")
        try:
            from ui_enhancements import load_ui_prefs, patch_modern_ui
            if not getattr(ModernUI, '_ui_enh_patch', False):
                patch_modern_ui(ModernUI)
                ModernUI._ui_enh_patch = True
            _prefs = load_ui_prefs()
            ModernUI.apply_ui_prefs(root)
        except Exception:
            pass

        w, h = 620, 480
        x = (root.winfo_screenwidth() - w) // 2
        y = (root.winfo_screenheight() - h) // 2
        root.geometry(f"{w}x{h}+{x}+{y}")
        root.resizable(False, False)
        root.overrideredirect(True)
        root.configure(bg=ModernUI.COLORS['bg_primary'])
        ModernUI._root_ref = root

        try:
            root.attributes('-alpha', 0.0)
            def _fade(step=0):
                a = min(1.0, step / 10.0)
                try:
                    root.attributes('-alpha', a)
                except Exception:
                    return
                if a < 1.0:
                    root.after(20, lambda: _fade(step + 1))
            root.after(40, _fade)
        except Exception:
            pass

        base = ModernUI._base_path()
        try:
            ico = os.path.join(base, 'assets', 'logo.ico')
            if os.path.exists(ico):
                root.iconbitmap(ico)
        except Exception:
            pass
        try:
            for png_name in ('argus-wordmark.png', 'logo.png'):
                png = os.path.join(base, 'assets', png_name)
                if os.path.exists(png) and _PIL_OK:
                    _img = Image.open(png).convert('RGBA')
                    iw, ih = _img.size
                    side = 32
                    nh = side
                    nw = max(side, int(iw * nh / max(ih, 1)))
                    _img = _img.resize((nw, nh), Image.LANCZOS)
                    _photo = ImageTk.PhotoImage(_img)
                    root.iconphoto(True, _photo)
                    root._icon_ref = _photo
                    break
        except Exception:
            pass

        root.update_idletasks()
        try:
            hwnd = ctypes.windll.user32.GetParent(root.winfo_id())
            if not hwnd:
                hwnd = root.winfo_id()
            GWL_EXSTYLE = -20
            WS_EX_APPWINDOW = 0x00040000
            WS_EX_TOOLWINDOW = 0x00000080
            style = ctypes.windll.user32.GetWindowLongW(hwnd, GWL_EXSTYLE)
            style = (style & ~WS_EX_TOOLWINDOW) | WS_EX_APPWINDOW
            ctypes.windll.user32.SetWindowLongW(hwnd, GWL_EXSTYLE, style)
            root.withdraw()
            root.after(15, root.deiconify)

            RADIUS = 16
            ww = root.winfo_width() or w
            hh = root.winfo_height() or h
            hrgn = ctypes.windll.gdi32.CreateRoundRectRgn(0, 0, ww + 1, hh + 1, RADIUS * 2, RADIUS * 2)
            if hrgn:
                ctypes.windll.user32.SetWindowRgn(hwnd, hrgn, True)
            try:
                pref = ctypes.c_int(2)
                ctypes.windll.dwmapi.DwmSetWindowAttribute(hwnd, 33, ctypes.byref(pref), ctypes.sizeof(pref))
            except Exception:
                pass
            try:
                border_colorref = ctypes.c_int(0x00FF7B8B)  # BGR #8b7bff
                ctypes.windll.dwmapi.DwmSetWindowAttribute(
                    hwnd, 34, ctypes.byref(border_colorref), ctypes.sizeof(border_colorref))
            except Exception:
                pass
        except Exception:
            pass

        ModernUI._create_floating_bg(root)

        try:
            if not getattr(ModernUI, '_ui_enh_patch', False):
                from ui_enhancements import patch_modern_ui
                patch_modern_ui(ModernUI)
                ModernUI._ui_enh_patch = True
        except Exception:
            pass

    # ══════════════════════════════════════════════════════════════════════
    #  HEADER — Clean bar with eye icon
    # ══════════════════════════════════════════════════════════════════════
    @classmethod
    def create_header(cls, parent):
        C = cls.COLORS
        hdr = tk.Frame(parent, bg=C['bg_primary'])
        hdr.place(x=0, y=0, relwidth=1.0, height=40)
        hdr.lift()

        inner = tk.Frame(hdr, bg=C['bg_primary'])
        inner.pack(fill=tk.X, padx=16, pady=(8, 4))

        def _start_drag(ev):
            cls._drag_x = ev.x
            cls._drag_y = ev.y

        def _on_drag(ev):
            r = cls._root_ref
            if r is None:
                return
            try:
                x = r.winfo_x() + ev.x - cls._drag_x
                y = r.winfo_y() + ev.y - cls._drag_y
                r.geometry(f"+{x}+{y}")
            except Exception:
                pass

        for w in (hdr, inner):
            w.bind('<Button-1>', _start_drag)
            w.bind('<B1-Motion>', _on_drag)

        left = tk.Frame(inner, bg=C['bg_primary'])
        left.pack(side=tk.LEFT)

        # Logo cósmico ARGUS (sin emojis ni texto duplicado)
        create_wordmark_label(left, height=24, pack_opts={'side': tk.LEFT, 'padx': (0, 10)})

        if cls._app_version:
            tk.Label(left, text=f"v{cls._app_version}",
                     font=('Consolas', 8),
                     bg=C['bg_primary'], fg=C['text_muted']).pack(side=tk.LEFT)

        right = tk.Frame(inner, bg=C['bg_primary'])
        right.pack(side=tk.RIGHT)

        # Status badge — green dot + text
        badge_frame = tk.Frame(right, bg=C['bg_primary'])
        badge_frame.pack(side=tk.RIGHT, padx=(0, 4))

        badge_dot = tk.Canvas(badge_frame, width=7, height=7,
                              bg=C['bg_primary'], highlightthickness=0, bd=0)
        badge_dot.pack(side=tk.LEFT, padx=(0, 4), pady=1)
        badge_dot.create_oval(1, 1, 6, 6, fill=C['green'], outline='')

        badge = tk.Label(badge_frame, text="ONLINE",
                         font=('Segoe UI', 7, 'bold'),
                         bg=C['bg_primary'], fg=C['green'])
        badge.pack(side=tk.LEFT)
        cls._status_badge = badge
        cls._status_badge_canvas = badge_dot

        r = cls._root_ref
        chrome = tk.Frame(right, bg=C['bg_primary'])
        chrome.pack(side=tk.RIGHT, padx=(0, 8))

        def _chrome_btn(text, cmd, hover_fg=None):
            b = tk.Label(chrome, text=text, font=('Segoe UI', 10),
                         bg=C['bg_primary'], fg=C['text_muted'],
                         padx=4, cursor='hand2')
            b.pack(side=tk.LEFT, padx=1)
            b.bind('<Button-1>', lambda _e: cmd())
            hf = hover_fg or C['text_secondary']
            b.bind('<Enter>', lambda _e: b.config(fg=hf))
            b.bind('<Leave>', lambda _e: b.config(fg=C['text_muted']))
            return b

        if r is not None:
            def _close_app():
                cb = cls._quit_callback
                if callable(cb):
                    cb()
                else:
                    r.destroy()

            _chrome_btn('\u2014', lambda: r.iconify())
            _chrome_btn('\u2715', _close_app, hover_fg=C['red'])

        sep = tk.Frame(hdr, bg=C['border'], height=1)
        sep.pack(fill=tk.X, side=tk.BOTTOM)

        try:
            cls.enhance_header(hdr, inner, right)
        except Exception:
            pass

        return hdr

    # ══════════════════════════════════════════════════════════════════════
    #  SISTEMA SOLAR — indicador de carga (sin canvas negro)
    # ══════════════════════════════════════════════════════════════════════
    @classmethod
    def _stop_solar_animation(cls):
        if cls._orbit_after_id and cls._orbit_canvas:
            try:
                cls._orbit_canvas.after_cancel(cls._orbit_after_id)
            except Exception:
                pass
        cls._orbit_after_id = None

    @classmethod
    def _solar_tick(cls):
        canvas = cls._orbit_canvas
        if canvas is None:
            return
        try:
            if not canvas.winfo_exists():
                return
            cx, cy = cls._solar_cx, cls._solar_cy
            for p in cls._solar_planets:
                p['angle'] += p['speed']
                x = cx + p['r'] * math.cos(p['angle'])
                y = cy + p['r'] * math.sin(p['angle'])
                s = p['size']
                canvas.coords(p['id'], x - s, y - s, x + s, y + s)
                hs = s + 2
                canvas.coords(p['halo'], x - hs, y - hs, x + hs, y + hs)
            cls._orbit_after_id = canvas.after(42, cls._solar_tick)
        except Exception:
            pass

    @classmethod
    def _start_solar_animation(cls):
        cls._stop_solar_animation()
        if cls._scan_bg_reduced_motion():
            return
        cls._solar_tick()

    @classmethod
    def _build_solar_system(cls, canvas, cx, cy, r_outer=78):
        """Dibuja sol, órbitas y planetas sobre el fondo animado."""
        C = cls.COLORS
        tag = 'solar'
        canvas.delete(tag)
        cls._stop_solar_animation()

        cls._orbit_canvas = canvas
        cls._solar_cx, cls._solar_cy, cls._solar_r = cx, cy, r_outer
        cls._solar_planets = []

        rings = (r_outer, r_outer - 24, r_outer - 42)
        for ro in rings:
            canvas.create_oval(
                cx - ro, cy - ro, cx + ro, cy + ro,
                outline='#2a2850', width=1, tags=tag,
            )

        cls._orbit_track = canvas.create_oval(
            cx - r_outer, cy - r_outer, cx + r_outer, cy + r_outer,
            outline='#3d3580', width=2, tags=tag,
        )
        cls._orbit_arc = canvas.create_arc(
            cx - r_outer, cy - r_outer, cx + r_outer, cy + r_outer,
            start=90, extent=0, outline=C['accent_light'], width=3,
            style='arc', tags=tag,
        )

        for sr, col in ((16, '#3d3580'), (11, C['accent']), (7, C['accent_light']), (4, '#ECEDFF')):
            canvas.create_oval(
                cx - sr, cy - sr, cx + sr, cy + sr,
                fill=col, outline='', tags=tag,
            )

        cls._orbit_pct_text = canvas.create_text(
            cx, cy - 2, text='0',
            font=('Segoe UI', 32, 'bold'),
            fill=C['text_primary'], tags=tag,
        )
        cls._orbit_pct_sign = canvas.create_text(
            cx + 28, cy + 6, text='%',
            font=('Segoe UI', 13),
            fill=C['text_muted'], tags=tag,
        )

        planet_specs = (
            {'r': r_outer - 6, 'speed': 0.028, 'phase': 0.0, 'size': 5, 'color': C['accent_light']},
            {'r': r_outer - 26, 'speed': -0.02, 'phase': 2.1, 'size': 4, 'color': C['accent']},
            {'r': r_outer - 40, 'speed': 0.015, 'phase': 4.5, 'size': 3, 'color': C['gold']},
            {'r': r_outer - 16, 'speed': 0.045, 'phase': 1.0, 'size': 2, 'color': C['green_glow']},
        )
        for spec in planet_specs:
            ang = spec['phase']
            pr = spec['r']
            px = cx + pr * math.cos(ang)
            py = cy + pr * math.sin(ang)
            s = spec['size']
            body = canvas.create_oval(
                px - s, py - s, px + s, py + s,
                fill=spec['color'], outline=C['accent_deep'], width=1, tags=tag,
            )
            halo = canvas.create_oval(
                px - s - 2, py - s - 2, px + s + 2, py + s + 2,
                outline=spec['color'], width=1, tags=tag,
            )
            cls._solar_planets.append({
                **spec, 'id': body, 'halo': halo, 'angle': ang,
            })

        cls._layout_hud_text(canvas)
        cls._sync_hud_proxies()
        cls._raise_scan_layers(canvas)
        cls._start_solar_animation()

    @classmethod
    def _sync_hud_proxies(cls):
        canvas = cls._section_bg_canvas
        for proxy, iid in (
            (getattr(cls, '_hud_status_proxy', None), cls._hud_status_id),
            (getattr(cls, '_hud_detail_proxy', None), cls._hud_detail_id),
            (getattr(cls, '_hud_timer_proxy', None), cls._hud_timer_id),
            (getattr(cls, '_hud_resources_proxy', None), cls._hud_resources_id),
        ):
            if proxy and iid and canvas:
                proxy._canvas = canvas
                proxy._item_id = iid

    @classmethod
    def _layout_hud_text(cls, canvas):
        """Texto y barra bajo el sol — todo en el canvas (sin cajas negras)."""
        C = cls.COLORS
        cx, cy, ro = cls._solar_cx, cls._solar_cy, cls._solar_r
        canvas.delete('hud')
        canvas.delete('hud_bar')

        cls._hud_bar_y = cy + ro + 72
        cls._hud_status_id = canvas.create_text(
            cx, cy + ro + 30, text='Iniciando escaneo...',
            font=('Segoe UI', 11), fill=C['text_primary'],
            tags='hud', anchor='center',
        )
        cls._hud_detail_id = canvas.create_text(
            cx, cy + ro + 52, text='Preparando sistema...',
            font=('Consolas', 9), fill=C['text_muted'],
            tags='hud', anchor='center',
        )
        cls._hud_timer_id = canvas.create_text(
            cx, cls._hud_bar_y + 28, text='00:00:00',
            font=('Consolas', 13, 'bold'), fill=C['accent_light'],
            tags='hud', anchor='center',
        )
        cls._hud_resources_id = canvas.create_text(
            cx, cls._hud_bar_y + 50, text='',
            font=('Segoe UI', 8), fill=C['text_muted'],
            tags='hud', anchor='center',
        )
        cls._draw_hud_bar(0)

    @classmethod
    def _draw_hud_bar(cls, pct_val):
        canvas = cls._section_bg_canvas
        if canvas is None:
            return
        C = cls.COLORS
        cx, y = cls._solar_cx, cls._hud_bar_y
        half = 130
        canvas.delete('hud_bar')
        canvas.create_rectangle(
            cx - half, y, cx + half, y + 3,
            fill=C['border'], outline='', tags='hud_bar',
        )
        fw = max(0, int(half * 2 * float(pct_val) / 100))
        if fw > 0:
            canvas.create_rectangle(
                cx - half, y, cx - half + fw, y + 3,
                fill=C['accent'], outline='', tags='hud_bar',
            )
            tip = min(14, fw)
            canvas.create_rectangle(
                cx - half + fw - tip, y, cx - half + fw, y + 3,
                fill=C['accent_light'], outline='', tags='hud_bar',
            )
        cls._raise_scan_layers(canvas)

    @classmethod
    def _attach_solar_system(cls, parent):
        canvas = cls._section_bg_canvas
        if canvas is None:
            return

        def _reposition(_e=None):
            try:
                ch = max(parent.winfo_height(), 360)
                cw = max(parent.winfo_width(), 400)
                key = (cw, ch)
                if key == cls._solar_layout_key:
                    return
                cls._solar_layout_key = key
                cx, cy = cw // 2, 34 + int((ch - 34) * 0.34)
                cls._build_solar_system(canvas, cx, cy, r_outer=min(78, int(cw * 0.12)))
            except Exception:
                pass

        def _reposition_debounced(_e=None):
            if cls._solar_reposition_after and cls._root_ref:
                try:
                    cls._root_ref.after_cancel(cls._solar_reposition_after)
                except Exception:
                    pass
            r = cls._root_ref or parent
            cls._solar_reposition_after = r.after(120, _reposition)

        parent.bind('<Configure>', _reposition_debounced, add='+')
        parent.after(150, _reposition)

    @classmethod
    def _update_orbit_pct(cls, pct_val):
        if cls._orbit_canvas is None:
            return
        try:
            iv = int(pct_val)
            cls._orbit_canvas.itemconfig(cls._orbit_pct_text, text=str(iv))
            tx_bbox = cls._orbit_canvas.bbox(cls._orbit_pct_text)
            if tx_bbox:
                cls._orbit_canvas.coords(cls._orbit_pct_sign,
                                         tx_bbox[2] + 4,
                                         (tx_bbox[1] + tx_bbox[3]) // 2 + 6)
            arc = getattr(cls, '_orbit_arc', None)
            if arc is not None:
                extent = max(0, min(360, int(360 * iv / 100)))
                cls._orbit_canvas.itemconfig(arc, extent=-extent)
        except Exception:
            pass

    # ══════════════════════════════════════════════════════════════════════
    #  PROGRESS SECTION (scan view)
    # ══════════════════════════════════════════════════════════════════════
    @classmethod
    def create_progress_section(cls, parent):
        cls._apply_ttk_style()
        C = cls.COLORS

        outer = tk.Frame(parent, bg=C['bg_primary'])
        outer.place(x=0, y=40, relwidth=1.0, relheight=1.0)
        outer.lift()

        cls._create_section_bg(outer)

        # Barra superior
        top = tk.Frame(outer, bg=C['bg_secondary'], height=34)
        top.place(x=0, y=0, relwidth=1.0, height=34)
        top.pack_propagate(False)
        cls._progress_top_bar = top

        tk.Label(
            top, text='PROGRESO DEL ESCANEO',
            font=('Segoe UI', 7, 'bold'),
            bg=C['bg_secondary'], fg=C['text_muted'],
        ).pack(side=tk.LEFT, padx=(14, 0), pady=8)

        cancel_row = tk.Frame(top, bg=C['bg_secondary'])
        cancel_row.pack(side=tk.RIGHT, padx=(0, 10), pady=4)
        cancel_btn = tk.Button(
            cancel_row, text='Cancelar escaneo',
            font=('Segoe UI', 8),
            bg=C['bg_secondary'], fg=C['text_secondary'],
            activebackground=C['bg_hover'],
            activeforeground=C['red'],
            relief=tk.FLAT, bd=0, cursor='hand2',
            padx=6, pady=2,
        )
        cancel_btn.pack(side=tk.RIGHT)

        files_lbl = tk.Label(
            top, text='0 archivos',
            font=('Consolas', 8),
            bg=C['bg_secondary'], fg=C['text_muted'],
        )
        files_lbl.pack(side=tk.RIGHT, padx=(0, 14), pady=8)
        cls._files_count_label = files_lbl

        tk.Frame(outer, bg=C['border'], height=1).place(x=0, y=34, relwidth=1.0, height=1)

        canvas = cls._section_bg_canvas
        cls._hud_status_proxy = _CanvasTextProxy(canvas, 0)
        cls._hud_detail_proxy = _CanvasTextProxy(canvas, 0)
        cls._hud_timer_proxy = _CanvasTextProxy(canvas, 0)
        cls._hud_resources_proxy = _CanvasTextProxy(canvas, 0)
        cls._status_label_ref = cls._hud_status_proxy
        cls._detail_label_ref = cls._hud_detail_proxy
        cls._timer_widget = cls._hud_timer_proxy

        cls._attach_solar_system(outer)

        def _draw_bar(pct_val):
            cls._draw_hud_bar(pct_val)
            cls._update_orbit_pct(pct_val)

        bar_c = _CanvasBarProxy(_draw_bar)

        cls._counter_labels = {}
        for key in ('critical', 'suspicious', 'low', 'clean'):
            cls._counter_labels[key] = tk.Label(
                outer, text='',
                bg=C['bg_primary'], fg=C['bg_primary'],
            )

        cls._risk_canvas = None
        cls._risk_label = None
        cls._cpu_bar_canvas = None
        cls._ram_bar_canvas = None
        cls._phase_dots_canvas = None

        pb = ttk.Progressbar(
            outer, mode='determinate', maximum=100,
            style='Argus.Horizontal.TProgressbar',
        )

        return {
            'container':  outer,
            'card':       outer,
            'status':     cls._hud_status_proxy,
            'progress':   pb,
            'detail':     cls._hud_detail_proxy,
            'timer':      cls._hud_timer_proxy,
            'resources':  cls._hud_resources_proxy,
            'percent':    None,
            '_canvas':    bar_c,
            '_ring':      bar_c,
            'cancel_row': cancel_row,
            'cancel_btn': cancel_btn,
        }

    # ══════════════════════════════════════════════════════════════════════
    #  COMPLETION PANEL
    # ══════════════════════════════════════════════════════════════════════
    @classmethod
    def create_completion_panel(cls, parent):
        C = cls.COLORS
        outer = tk.Frame(parent, bg=C['bg_primary'])

        center = tk.Frame(outer, bg=C['bg_primary'])
        center.place(relx=0.5, rely=0.45, anchor='center')

        icon_c = tk.Canvas(center, width=56, height=56,
                           bg=C['bg_primary'], highlightthickness=0)
        icon_c.pack(pady=(0, 14))
        icon_c.create_oval(2, 2, 54, 54, outline=C['border_bright'], width=1, fill=C['bg_primary'])

        main_lbl = tk.Label(center, text="Esperando inicio",
                            font=('Segoe UI', 15, 'bold'),
                            bg=C['bg_primary'], fg=C['text_secondary'])
        main_lbl.pack()

        sub_lbl = tk.Label(center, text="",
                           font=('Segoe UI', 9),
                           bg=C['bg_primary'], fg=C['text_muted'])
        sub_lbl.pack(pady=(6, 0))

        top_find = tk.Label(center, text="",
                            font=('Consolas', 7),
                            bg=C['bg_primary'], fg=C['accent_light'],
                            wraplength=380, justify='center')
        top_find.pack(pady=(10, 0))
        cls._top_finding_label = top_find

        outer.pack_forget()

        widgets = {
            'outer':       outer,
            'card':        outer,
            'icon_canvas': icon_c,
            'main_label':  main_lbl,
            'sub_label':   sub_lbl,
            'top_finding': top_find,
        }
        try:
            cls.enhance_completion_panel(widgets)
        except Exception:
            pass
        return widgets

    @classmethod
    def show_completion_panel(cls, completion_widgets, visible=True):
        outer = (completion_widgets or {}).get('outer')
        if outer is None:
            return
        try:
            if visible:
                outer.pack(fill=tk.BOTH, expand=True, padx=24, pady=(4, 10))
                outer.lift()
            else:
                outer.pack_forget()
        except Exception:
            pass

    @classmethod
    def set_scan_ui_mode(cls, progress_widgets=None, completion_widgets=None, scanning=True):
        if progress_widgets:
            cont = progress_widgets.get('container')
            if cont is not None:
                try:
                    if scanning:
                        cont.place(x=0, y=40, relwidth=1.0, relheight=1.0)
                        cont.lift()
                    else:
                        cont.place_forget()
                except Exception:
                    pass
        cls.show_completion_panel(completion_widgets, visible=not scanning)

    # ══════════════════════════════════════════════════════════════════════
    #  BUTTON
    # ══════════════════════════════════════════════════════════════════════
    @classmethod
    def create_button(cls, parent, text, command, style='primary', icon=''):
        C = cls.COLORS
        label = f"{icon}  {text}" if icon else text
        if style == 'primary':
            bg, hv, fg = C['accent'], C['accent_hover'], '#FFFFFF'
            px, py, fs = 28, 11, 10
        elif style == 'secondary':
            bg, hv, fg = C['bg_card'], C['bg_hover'], C['text_primary']
            px, py, fs = 18, 8, 9
        else:
            bg, hv, fg = C['bg_secondary'], C['bg_card'], C['text_secondary']
            px, py, fs = 14, 6, 8

        frame = tk.Frame(parent, bg=C['bg_primary'])
        btn = tk.Button(frame, text=label, command=command,
                        bg=bg, fg=fg, font=('Segoe UI', fs, 'bold'),
                        padx=px, pady=py, relief=tk.FLAT, bd=0,
                        cursor='hand2', activebackground=hv,
                        activeforeground=fg, highlightthickness=0)
        btn.pack(fill=tk.X)
        btn.bind('<Enter>', lambda _: btn.config(bg=hv))
        btn.bind('<Leave>', lambda _: btn.config(bg=bg))
        return frame

    # ══════════════════════════════════════════════════════════════════════
    #  RESULTS SECTION
    # ══════════════════════════════════════════════════════════════════════
    @classmethod
    def create_results_section(cls, parent):
        C = cls.COLORS
        hidden = tk.Frame(parent, bg=C['bg_primary'], height=0)
        hidden.pack()
        hidden.pack_propagate(False)
        ta = scrolledtext.ScrolledText(hidden, wrap=tk.WORD,
                                       font=cls.FONTS['mono'],
                                       bg=C['bg_card'], fg=C['text_primary'],
                                       relief=tk.FLAT, bd=0)
        ta.pack(fill=tk.BOTH, expand=True)
        for tag, color in [('success', C['green']), ('warning', C['amber']),
                           ('danger', C['red']), ('info', C['blue']),
                           ('header', C['text_primary']), ('muted', C['text_secondary']),
                           ('accent', C['accent'])]:
            ta.tag_config(tag, foreground=color)
        title = tk.Label(hidden, text='', bg=C['bg_primary'])
        return {'container': hidden, 'text': ta, 'title': title}

    # ══════════════════════════════════════════════════════════════════════
    #  PUBLIC HELPERS
    # ══════════════════════════════════════════════════════════════════════
    @classmethod
    def format_phase_label(cls, text, max_len=52):
        if not text:
            return ""
        one_line = sanitize_ui_text(str(text))
        return one_line[:max_len - 1] + "\u2026" if len(one_line) > max_len else one_line

    @classmethod
    def set_status_badge(cls, text, color=None):
        if cls._status_badge is None:
            return
        col = color or cls.COLORS['accent']
        try:
            cls._status_badge.config(text=(text or '').upper(), fg=col)
            if cls._status_badge_canvas:
                cls._status_badge_canvas.delete('all')
                cls._status_badge_canvas.create_oval(1, 1, 6, 6, fill=col, outline='')
        except Exception:
            pass

    _counter_short = {'critical': 'CRIT', 'suspicious': 'SOSP', 'low': 'BAJO', 'clean': 'OK'}

    @classmethod
    def update_counter(cls, key, value):
        lbl = cls._counter_labels.get(key)
        if lbl is None:
            return
        short = cls._counter_short.get(key, key.upper()[:4])
        try:
            lbl.config(text=f"{short}: {int(value)}")
        except Exception:
            pass

    @classmethod
    def update_phase_dots(cls, pct):
        pass

    @classmethod
    def update_status_fade(cls, status_text=None, detail_text=None):
        if status_text is not None and cls._status_label_ref:
            try:
                cls._status_label_ref.config(text=status_text)
            except Exception:
                pass
        if detail_text is not None and cls._detail_label_ref:
            try:
                cls._detail_label_ref.config(text=detail_text)
            except Exception:
                pass
        if detail_text:
            try:
                cls.append_phase_history(detail_text)
            except Exception:
                pass

    @classmethod
    def update_risk_meter(cls, score, crit_count=0):
        pass

    @classmethod
    def update_resource_meters(cls, cpu_pct=None, ram_pct=None):
        pass

    @classmethod
    def set_top_finding(cls, completion_widgets, text):
        lbl = (completion_widgets or {}).get('top_finding') or cls._top_finding_label
        if lbl is None:
            return
        try:
            lbl.config(text=text[:120] if text else '')
        except Exception:
            pass

    @classmethod
    def update_canvas_bar(cls, canvas, pct_val):
        try:
            cls._ring_pct = float(pct_val)
            if hasattr(canvas, '_draw'):
                canvas._draw(pct_val)
            else:
                cls._draw_hud_bar(pct_val)
                cls._update_orbit_pct(pct_val)
        except Exception:
            pass

    @classmethod
    def set_completion_state(cls, completion_widgets, success=True, message=None, sub=None, counts=None):
        C = cls.COLORS
        icon_c = completion_widgets.get('icon_canvas')
        main_lbl = completion_widgets.get('main_label')
        sub_lbl = completion_widgets.get('sub_label')

        if icon_c:
            icon_c.delete('all')
            color = C['green'] if success else C['red_deep']
            icon_c.create_oval(2, 2, 54, 54, outline=color, width=1.5, fill=C['bg_primary'])
            if success:
                icon_c.create_line(16, 27, 24, 37, 38, 17,
                                   fill=color, width=2.5,
                                   joinstyle='round', capstyle='round')
            else:
                icon_c.create_line(17, 17, 39, 39, fill=color, width=2.5, capstyle='round')
                icon_c.create_line(39, 17, 17, 39, fill=color, width=2.5, capstyle='round')

        if main_lbl:
            txt = message or ("Escaneo completado" if success else "Error en el escaneo")
            main_lbl.config(text=txt, fg=C['green'] if success else C['red_deep'])

        if sub_lbl:
            if counts:
                crit = int(counts.get('critical', 0))
                susp = int(counts.get('suspicious', 0))
                low = int(counts.get('low', 0))
                total = int(counts.get('total', crit + susp + low + int(counts.get('clean', 0))))
                parts = [f"CRIT {crit}", f"SOSP {susp}"]
                if low:
                    parts.append(f"BAJO {low}")
                parts.append(f"Total {total}")
                line = " \u00b7 ".join(parts)
                if sub:
                    line = f"{line} \u2014 {sub}"
                sub_lbl.config(text=line, fg=C['text_secondary'])
            else:
                sub_lbl.config(text=sub or "", fg=C['text_secondary'])

        try:
            cls.flash_dwm_border(success and int((counts or {}).get('critical', 0)) == 0)
            if success:
                cls.play_complete_sound()
        except Exception:
            pass

    # Stubs for ambient motion (unused in v5)
    @classmethod
    def _start_ambient_motion(cls, *a, **kw):
        pass

    @classmethod
    def _stop_ambient_motion(cls):
        pass

    @classmethod
    def _start_badge_pulse(cls, *a):
        pass

    @classmethod
    def _stop_badge_pulse(cls):
        pass

    @classmethod
    def _start_pct_tween(cls):
        pass
