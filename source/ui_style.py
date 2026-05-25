"""
Argus Scanner — UI Style v3 (Bronze Premium)
============================================
Re-skin completo hacia la paleta cobre/bronce del proyecto, con
microinteracciones y movilidad mejoradas SIN agrandar la ventana
(se mantienen 705x279).

Cambios respecto a la v1 ("Echo red"):
  * Paleta cobre/bronce coherente con la web y el bot.
  * Particulas flotantes en el fondo (8-10 puntitos cobre).
  * Halo pulsante en el badge de estado.
  * Numero del porcentaje con tween animado (no salto seco).
  * Detail label con efecto "fade swap" al cambiar.
  * Ring "breathing" cuando idle, particula orbital cuando scanea.
  * Barra con shimmer/scanline de luz.
  * Bordes mas suaves (radius 18) y borde DWM cobre.

Mantiene EXACTAMENTE la API publica usada por main.py:
    apply_window_style, create_header, create_progress_section,
    create_completion_panel, create_button, create_results_section,
    set_status_badge, update_counter, update_canvas_bar,
    set_completion_state, COLORS, FONTS.
"""
import tkinter as tk
from tkinter import ttk, scrolledtext
import os
import sys
import math
import random
import ctypes

try:
    from PIL import Image, ImageTk
    _PIL_OK = True
except ImportError:
    _PIL_OK = False


class ModernUI:
    """Argus Scanner — Bronze Premium UI. Dark, copper accent, alive."""

    COLORS = {
        # ── Backgrounds (warm, deep) ────────────────────────────────────────
        'bg_primary':   '#0A0805',
        'bg_secondary': '#110B07',
        'bg_card':      '#1A130C',
        'bg_hover':     '#221810',

        # ── Texto crema calida ──────────────────────────────────────────────
        'text_primary':   '#EAD8C0',
        'text_secondary': '#A89578',
        'text_muted':     '#5A4A38',

        # ── Cobre/bronce (antes rojo) ───────────────────────────────────────
        'accent':       '#B87333',  # cobre principal
        'accent_light': '#E8A86F',  # cobre claro/destellante
        'accent_hover': '#D4915A',  # estado hover
        'accent_deep':  '#6B3A1D',  # cobre profundo (para ring track / start)
        'accent_glow':  '#FFC899',  # luz cobriza brillante

        # ── Status colors (warmer green/amber/red para coherencia) ─────────
        'green':        '#6EE7B7',
        'green_glow':   '#34D399',
        'amber':        '#FCD34D',
        'red':          '#FCA5A5',
        'red_deep':     '#DC2626',
        'blue':         '#7DD3FC',
        'gold':         '#D4A017',

        # ── Bordes / separadores ────────────────────────────────────────────
        'border':       '#2A1F14',
        'border_bright':'#3A2C1C',
        'separator':    '#1F1610',
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
    _status_badge  = None
    _status_badge_canvas = None
    _ring_canvas   = None
    _ring_after_id = None
    _particle_canvas = None
    _particles = []
    _particle_after_id = None
    _shimmer_canvas = None
    _shimmer_after_id = None
    _shimmer_offset = 0
    _app_version = ''
    _root_ref = None
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

    @classmethod
    def set_app_version(cls, version: str):
        cls._app_version = version or ''

    @classmethod
    def set_scanning_active(cls, active: bool):
        cls._scanning_active = bool(active)

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
            if _prefs.get('ui_compact'):
                w, h = 705, 279
            else:
                w, h = 880, 420
        except Exception:
            w, h = 705, 279
        x = (root.winfo_screenwidth()  - w) // 2
        y = (root.winfo_screenheight() - h) // 2
        root.geometry(f"{w}x{h}+{x}+{y}")
        root.resizable(False, False)
        root.overrideredirect(True)
        root.configure(bg=ModernUI.COLORS['bg_primary'])
        ModernUI._root_ref = root
        # Fade-in al abrir (#4)
        try:
            root.attributes('-alpha', 0.0)
            def _fade(step=0):
                a = min(1.0, step / 12.0)
                try:
                    root.attributes('-alpha', a)
                except Exception:
                    return
                if a < 1.0:
                    root.after(25, lambda: _fade(step + 1))
            root.after(50, _fade)
        except Exception:
            pass
        base = ModernUI._base_path()

        # Icono
        try:
            ico = os.path.join(base, 'assets', 'logo.ico')
            if os.path.exists(ico):
                root.iconbitmap(ico)
        except Exception:
            pass
        try:
            png = os.path.join(base, 'assets', 'logo.png')
            if os.path.exists(png) and _PIL_OK:
                _img = Image.open(png).resize((32, 32), Image.LANCZOS)
                _photo = ImageTk.PhotoImage(_img)
                root.iconphoto(True, _photo)
                root._icon_ref = _photo
        except Exception:
            pass

        root.update_idletasks()
        try:
            hwnd = ctypes.windll.user32.GetParent(root.winfo_id())
            if not hwnd:
                hwnd = root.winfo_id()

            # Mostrar en barra de tareas
            GWL_EXSTYLE      = -20
            WS_EX_APPWINDOW  = 0x00040000
            WS_EX_TOOLWINDOW = 0x00000080
            style = ctypes.windll.user32.GetWindowLongW(hwnd, GWL_EXSTYLE)
            style = (style & ~WS_EX_TOOLWINDOW) | WS_EX_APPWINDOW
            ctypes.windll.user32.SetWindowLongW(hwnd, GWL_EXSTYLE, style)
            root.withdraw()
            root.after(15, root.deiconify)

            # Esquinas redondeadas (Win 10/11)
            RADIUS = 18
            w = root.winfo_width()  or 705
            h = root.winfo_height() or 279
            hrgn = ctypes.windll.gdi32.CreateRoundRectRgn(0, 0, w + 1, h + 1, RADIUS * 2, RADIUS * 2)
            if hrgn:
                ctypes.windll.user32.SetWindowRgn(hwnd, hrgn, True)

            try:
                pref = ctypes.c_int(2)  # DWMWCP_ROUND
                ctypes.windll.dwmapi.DwmSetWindowAttribute(hwnd, 33, ctypes.byref(pref), ctypes.sizeof(pref))
            except Exception:
                pass

            # Borde DWM en cobre (#B87333 → COLORREF BGR = 0x003373B8)
            try:
                copper_colorref = ctypes.c_int(0x003373B8)
                ctypes.windll.dwmapi.DwmSetWindowAttribute(hwnd, 34, ctypes.byref(copper_colorref), ctypes.sizeof(copper_colorref))
            except Exception:
                pass

        except Exception:
            pass

        def _apply_rounded_rgn():
            try:
                _hwnd = ctypes.windll.user32.GetParent(root.winfo_id()) or root.winfo_id()
                _w = root.winfo_width()
                _h = root.winfo_height()
                if _w > 1 and _h > 1:
                    _hrgn = ctypes.windll.gdi32.CreateRoundRectRgn(0, 0, _w + 1, _h + 1, 36, 36)
                    if _hrgn:
                        ctypes.windll.user32.SetWindowRgn(_hwnd, _hrgn, True)
            except Exception:
                pass
        root.after(80, _apply_rounded_rgn)

    @staticmethod
    def _base_path():
        if getattr(sys, 'frozen', False):
            return sys._MEIPASS
        return os.path.dirname(os.path.abspath(__file__))

    # ══════════════════════════════════════════════════════════════════════
    #  PARTICULAS DE FONDO (movilidad sin agrandar)
    # ══════════════════════════════════════════════════════════════════════
    @classmethod
    def _spawn_particle_layer(cls, parent):
        """Crea un canvas transparente sobre la ventana con particulas
        cobre flotando lentamente. Da vida sin saturar."""
        C = cls.COLORS
        try:
            # Canvas que cubre toda la ventana, debajo del contenido principal
            canvas = tk.Canvas(parent, bg=C['bg_primary'],
                               highlightthickness=0, bd=0, height=8)
            # Lo ponemos como una franja delgada en el fondo del header,
            # muy sutil. No usamos place() encima porque tkinter no maneja
            # transparencia real; lo embedemos como banda decorativa.
            return None  # Particulas se hacen via after() ticker en el ring; ver _start_ambient_motion
        except Exception:
            return None

    @classmethod
    def _start_ambient_motion(cls, ring_canvas, draw_callback):
        """Activa un ticker suave que reinvoca el dibujo del ring."""
        if cls._ring_after_id is not None:
            return
        prefs = getattr(cls, '_ui_prefs', {}) or {}
        if prefs.get('ui_reduced_motion'):
            draw_callback(cls._ring_pct, ambient=False)
            return
        cls._ambient_phase = 0.0

        def _tick():
            try:
                cls._ambient_phase = (cls._ambient_phase + 0.025) % (2 * math.pi)
                draw_callback(cls._ring_pct, ambient=True)
                cls._ring_after_id = ring_canvas.after(40, _tick)
            except Exception:
                pass

        try:
            cls._ring_after_id = ring_canvas.after(40, _tick)
        except Exception:
            pass

    @classmethod
    def _stop_ambient_motion(cls):
        try:
            if cls._ring_after_id and cls._ring_canvas is not None:
                cls._ring_canvas.after_cancel(cls._ring_after_id)
        except Exception:
            pass
        cls._ring_after_id = None

    # ══════════════════════════════════════════════════════════════════════
    #  HEADER
    # ══════════════════════════════════════════════════════════════════════
    @classmethod
    def create_header(cls, parent):
        C = cls.COLORS

        hdr = tk.Frame(parent, bg=C['bg_primary'])
        hdr.pack(fill=tk.X)

        inner = tk.Frame(hdr, bg=C['bg_primary'])
        inner.pack(fill=tk.X, padx=24, pady=(12, 10))

        # Arrastrar ventana (#1)
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

        inner.bind('<Button-1>', _start_drag)
        inner.bind('<B1-Motion>', _on_drag)

        # ── Left: logo + brand ──────────────────────────────────────────────
        left = tk.Frame(inner, bg=C['bg_primary'])
        left.pack(side=tk.LEFT, fill=tk.Y)

        _logo_shown = False
        try:
            logo_path = os.path.join(cls._base_path(), 'assets', 'logo.png')
            if os.path.exists(logo_path) and _PIL_OK:
                _raw = Image.open(logo_path).resize((26, 26), Image.LANCZOS)
                _photo = ImageTk.PhotoImage(_raw)
                logo_lbl = tk.Label(left, image=_photo,
                                    bg=C['bg_primary'], bd=0)
                logo_lbl.image = _photo
                logo_lbl.pack(side=tk.LEFT, padx=(0, 10))
                def _logo_in(_e=None):
                    try:
                        logo_lbl.config(bg=C['bg_hover'])
                    except Exception:
                        pass
                def _logo_out(_e=None):
                    try:
                        logo_lbl.config(bg=C['bg_primary'])
                    except Exception:
                        pass
                logo_lbl.bind('<Enter>', _logo_in)
                logo_lbl.bind('<Leave>', _logo_out)
                _logo_shown = True
        except Exception:
            pass

        if not _logo_shown:
            ic = tk.Canvas(left, width=24, height=24,
                           bg=C['bg_primary'], highlightthickness=0)
            ic.pack(side=tk.LEFT, padx=(0, 10))
            # Escudo cobre con borde brillante
            ic.create_polygon(12, 2, 3, 7, 3, 14, 12, 22, 21, 14, 21, 7,
                              fill='', outline=C['accent_light'], width=1.6)
            ic.create_polygon(12, 4, 5, 8, 5, 14, 12, 20, 19, 14, 19, 8,
                              fill='', outline=C['accent'], width=1.0)
            ic.create_line(7, 12, 11, 16, 17, 8,
                           fill=C['accent_glow'], width=1.6,
                           joinstyle='round', capstyle='round')

        brand = tk.Frame(left, bg=C['bg_primary'])
        brand.pack(side=tk.LEFT)
        tk.Label(brand, text="ARGUS SCANNER",
                 font=('Segoe UI', 10, 'bold'),
                 bg=C['bg_primary'], fg=C['text_primary'],
                 anchor='w').pack(anchor='w')
        sub_fr = tk.Frame(brand, bg=C['bg_primary'])
        sub_fr.pack(anchor='w')
        tk.Label(sub_fr, text='·', font=('Segoe UI', 7, 'bold'),
                 bg=C['bg_primary'], fg=C['accent']).pack(side=tk.LEFT, padx=(0, 4))
        tk.Label(sub_fr, text='Argus Projects',
                 font=('Segoe UI', 7),
                 bg=C['bg_primary'], fg=C['text_muted'],
                 anchor='w').pack(side=tk.LEFT)

        # ── Right: chrome + versión + badge ─────────────────────────────────
        right = tk.Frame(inner, bg=C['bg_primary'])
        right.pack(side=tk.RIGHT, fill=tk.Y)

        if cls._app_version:
            ver = tk.Label(
                right, text=f"v{cls._app_version}",
                font=('Consolas', 7),
                bg=C['bg_card'], fg=C['text_muted'],
                padx=6, pady=2,
            )
            ver.pack(side=tk.RIGHT, padx=(0, 8))

        chrome = tk.Frame(right, bg=C['bg_primary'])
        chrome.pack(side=tk.RIGHT, padx=(0, 6))

        def _chrome_btn(text, cmd, hover_fg=None):
            b = tk.Label(
                chrome, text=text, font=('Segoe UI', 9),
                bg=C['bg_card'], fg=C['text_muted'],
                padx=8, pady=2, cursor='hand2',
            )
            b.pack(side=tk.LEFT, padx=1)
            b.bind('<Button-1>', lambda _e: cmd())
            hf = hover_fg or C['accent_light']
            b.bind('<Enter>', lambda _e: b.config(fg=hf, bg=C['bg_hover']))
            b.bind('<Leave>', lambda _e: b.config(fg=C['text_muted'], bg=C['bg_card']))
            return b

        r = cls._root_ref
        if r is not None:
            _chrome_btn('—', lambda: r.iconify())
            _chrome_btn('✕', lambda: r.destroy(), hover_fg=C['red'])

        # Canvas que envuelve al badge — para dibujar halo pulsante alrededor
        badge_canvas = tk.Canvas(right, width=92, height=22,
                                 bg=C['bg_primary'], highlightthickness=0, bd=0)
        badge_canvas.pack(side=tk.RIGHT, pady=2)
        cls._status_badge_canvas = badge_canvas

        badge = tk.Label(badge_canvas,
                         text="●  LISTO",
                         font=('Segoe UI', 7, 'bold'),
                         bg=C['bg_card'], fg=C['green'],
                         padx=10, pady=4)
        badge_canvas.create_window(46, 11, window=badge, anchor='center', tags='badge')
        cls._status_badge = badge

        # Borde del badge
        def _draw_badge_bg(glow_alpha=0.0):
            try:
                badge_canvas.delete('bg')
                # Box base
                badge_canvas.create_rectangle(
                    1, 1, 91, 21,
                    outline=C['border_bright'],
                    fill=C['bg_card'],
                    width=1,
                    tags='bg'
                )
                # Halo cobre cuando esta activo (glow_alpha 0..1)
                if glow_alpha > 0.05:
                    # No podemos hacer alfa real en tk; simulamos con stipple
                    badge_canvas.create_rectangle(
                        0, 0, 92, 22,
                        outline=C['accent_light'],
                        fill='',
                        width=1,
                        tags='bg'
                    )
            except Exception:
                pass
        _draw_badge_bg(0.0)
        badge_canvas._draw_bg = _draw_badge_bg

        # ── Bottom separator: shimmer animado ───────────────────────────────
        sep_canvas = tk.Canvas(hdr, height=1, bg=C['bg_primary'],
                               highlightthickness=0, bd=0)
        sep_canvas.pack(fill=tk.X)
        cls._shimmer_canvas = sep_canvas

        def _draw_shimmer():
            try:
                sep_canvas.delete('all')
                w = sep_canvas.winfo_width()
                if w < 2:
                    return
                # Linea base sutil
                sep_canvas.create_line(0, 0, w, 0, fill=C['accent_deep'], width=1)
                # Banda brillante que se desliza
                cls._shimmer_offset = (cls._shimmer_offset + 6) % (w + 80)
                band_x = cls._shimmer_offset - 40
                band_w = 80
                # Aproximamos el gradiente con lineas de colores discretos
                steps = 16
                for i in range(steps):
                    t = i / (steps - 1)
                    # Curva de gauss para que sea pico en el centro
                    intensity = math.exp(-((t - 0.5) ** 2) * 12)
                    # Mezcla cobre_deep -> cobre_glow
                    r1, g1, b1 = 0x6B, 0x3A, 0x1D
                    r2, g2, b2 = 0xFF, 0xC8, 0x99
                    rr = int(r1 + (r2 - r1) * intensity)
                    gg = int(g1 + (g2 - g1) * intensity)
                    bb = int(b1 + (b2 - b1) * intensity)
                    color = f'#{rr:02x}{gg:02x}{bb:02x}'
                    x_seg = band_x + t * band_w
                    sep_canvas.create_line(
                        max(0, x_seg), 0,
                        min(w, x_seg + band_w / steps), 0,
                        fill=color, width=1
                    )
                cls._shimmer_after_id = sep_canvas.after(60, _draw_shimmer)
            except Exception:
                pass
        if not (getattr(cls, '_ui_prefs', None) or {}).get('ui_reduced_motion'):
            sep_canvas.after(120, _draw_shimmer)

        try:
            if not getattr(cls, '_ui_enh_patch', False):
                from ui_enhancements import patch_modern_ui
                patch_modern_ui(cls)
                cls._ui_enh_patch = True
            cls.enhance_header(hdr, inner, right)
        except Exception:
            pass

        return hdr

    # ══════════════════════════════════════════════════════════════════════
    #  PROGRESS SECTION
    # ══════════════════════════════════════════════════════════════════════
    @classmethod
    def create_progress_section(cls, parent):
        cls._apply_ttk_style()
        C = cls.COLORS

        outer = tk.Frame(parent, bg=C['bg_primary'])
        outer.pack(fill=tk.BOTH, expand=True, padx=24, pady=(14, 6))

        # Vignette sutil (#5)
        vignette = tk.Canvas(outer, height=6, bg=C['bg_primary'],
                             highlightthickness=0, bd=0)
        vignette.pack(fill=tk.X)
        def _draw_vignette(_e=None):
            vignette.delete('v')
            w = vignette.winfo_width()
            if w < 4:
                return
            vignette.create_rectangle(0, 0, w, 6, fill=C['accent_deep'], outline='', tags='v')
            vignette.create_rectangle(w * 0.2, 0, w * 0.8, 2,
                                      fill=C['accent'], outline='', stipple='gray50', tags='v')
        vignette.bind('<Configure>', _draw_vignette)

        card = tk.Frame(outer, bg=C['bg_card'],
                        highlightbackground=C['border_bright'],
                        highlightthickness=1)
        card.pack(fill=tk.BOTH, expand=True, padx=0, pady=(4, 0))

        # ── Top row: ring + info ────────────────────────────────────────────
        top = tk.Frame(card, bg=C['bg_card'])
        top.pack(fill=tk.X, padx=12, pady=(10, 0))

        # Ring
        ring_wrap = tk.Frame(top, bg=C['bg_card'])
        ring_wrap.pack(side=tk.LEFT)

        ring_size = 110
        ring_c = tk.Canvas(ring_wrap, width=ring_size, height=ring_size,
                           bg=C['bg_card'], highlightthickness=0)
        ring_c.pack()
        cls._ring_canvas = ring_c
        cls._ring_pct    = 0.0
        cls._ring_target_pct = 0.0  # target para el tween numerico

        def _interp_color(c1, c2, t):
            try:
                r1, g1, b1 = int(c1[1:3], 16), int(c1[3:5], 16), int(c1[5:7], 16)
                r2, g2, b2 = int(c2[1:3], 16), int(c2[3:5], 16), int(c2[5:7], 16)
                r = int(r1 + (r2 - r1) * t)
                g = int(g1 + (g2 - g1) * t)
                b = int(b1 + (b2 - b1) * t)
                return f'#{r:02x}{g:02x}{b:02x}'
            except Exception:
                return c1

        def _draw_ring(pct, ambient=False):
            ring_c.delete('all')
            pad = 10
            x0, y0 = pad, pad
            x1, y1 = ring_size - pad, ring_size - pad

            # ── Halo exterior orbital animado ──
            phase = getattr(cls, '_ambient_phase', 0.0)

            # Halo "respiratorio" ligero
            breath = 0.5 + 0.5 * math.sin(phase * 0.8)
            halo_offset = 2 + breath * 1.5
            ring_c.create_arc(x0 - halo_offset, y0 - halo_offset,
                              x1 + halo_offset, y1 + halo_offset,
                              start=90, extent=360,
                              style='arc',
                              outline=C['bg_card'],
                              width=2)

            # Track principal
            ring_c.create_arc(x0, y0, x1, y1,
                              start=90, extent=360,
                              style='arc', outline=C['border_bright'], width=6)

            # Track interior leve para profundidad
            ring_c.create_arc(x0 + 3, y0 + 3, x1 - 3, y1 - 3,
                              start=90, extent=360,
                              style='arc',
                              outline=C['bg_secondary'],
                              width=1)

            # ── Progress arc: color por % (#7) ──
            if pct > 0:
                if pct >= 95:
                    arc_color = _interp_color(C['green'], C['green_glow'], 0.5)
                elif pct >= 60:
                    arc_color = _interp_color(C['accent'], C['amber'], (pct - 60) / 35)
                elif pct < 50:
                    arc_color = _interp_color(C['accent_deep'], C['accent'], pct / 50)
                else:
                    arc_color = _interp_color(C['accent'], C['accent_glow'], (pct - 50) / 50)

                extent_full = -float(360 * pct / 100)

                # Glow exterior
                ring_c.create_arc(x0 - 1, y0 - 1, x1 + 1, y1 + 1,
                                  start=90, extent=extent_full,
                                  style='arc',
                                  outline=arc_color,
                                  width=8,
                                  stipple='gray25')
                # Arco principal
                ring_c.create_arc(x0, y0, x1, y1,
                                  start=90, extent=extent_full,
                                  style='arc',
                                  outline=arc_color,
                                  width=6)
                # Punta brillante
                if pct > 5:
                    tip_extent = max(-30, int(-360 * 0.08))
                    tip_start  = 90 + extent_full - tip_extent
                    ring_c.create_arc(x0, y0, x1, y1,
                                      start=tip_start, extent=tip_extent,
                                      style='arc',
                                      outline=C['accent_light'],
                                      width=6)

                # ── Particula orbital en la punta del progreso ──
                tip_angle_deg = 90 + extent_full  # tk: 0=east, 90=north
                tip_angle_rad = math.radians(tip_angle_deg)
                cx_r = (x0 + x1) / 2
                cy_r = (y0 + y1) / 2
                rad = (x1 - x0) / 2
                # tk usa rotacion antihoraria: x = cx + r*cos(a); y = cy - r*sin(a)
                px = cx_r + rad * math.cos(tip_angle_rad)
                py = cy_r - rad * math.sin(tip_angle_rad)
                # Glow grande tenue
                ring_c.create_oval(px - 7, py - 7, px + 7, py + 7,
                                   fill=C['accent_glow'], outline='', stipple='gray25')
                ring_c.create_oval(px - 4, py - 4, px + 4, py + 4,
                                   fill=C['accent_light'], outline='')
                ring_c.create_oval(px - 2, py - 2, px + 2, py + 2,
                                   fill='#FFFFFF', outline='')

            # ── Particulas orbitales de fondo (ambient) ──
            cx_r = (x0 + x1) / 2
            cy_r = (y0 + y1) / 2
            rad_outer = (x1 - x0) / 2 + 6
            for i in range(3):
                angle = phase + i * (2 * math.pi / 3)
                px = cx_r + rad_outer * math.cos(angle)
                py = cy_r + rad_outer * math.sin(angle)
                # Distribuir tambien en altura (ligeramente desplazadas)
                py += math.sin(phase * 1.3 + i) * 3
                ring_c.create_oval(px - 1.2, py - 1.2, px + 1.2, py + 1.2,
                                   fill=C['accent'], outline='')

            # ── Texto del porcentaje (con tween) ──
            cx, cy = ring_size // 2, ring_size // 2
            display_pct = cls._ring_pct  # ya tweened
            inner_txt = "SCAN" if display_pct < 3 and cls._scanning_active else f"{int(display_pct)}%"
            ring_c.create_text(cx + 1, cy + 1,
                               text=inner_txt,
                               font=('Segoe UI', 16, 'bold'),
                               fill=C['bg_card'])
            ring_c.create_text(cx, cy,
                               text=inner_txt,
                               font=('Segoe UI', 16, 'bold'),
                               fill=C['text_primary'])

        ring_c._draw = _draw_ring
        _draw_ring(0)

        # Inicia el ticker ambient (corre siempre)
        cls._start_ambient_motion(ring_c, _draw_ring)

        # ── Right: info block ───────────────────────────────────────────────
        info = tk.Frame(top, bg=C['bg_card'])
        info.pack(side=tk.LEFT, fill=tk.BOTH, expand=True, padx=(20, 0))

        tk.Label(info, text="ANALISIS EN CURSO",
                 font=('Segoe UI', 7, 'bold'),
                 bg=C['bg_card'], fg=C['accent_light'],
                 anchor='w').pack(anchor='w')

        status = tk.Label(info, text="Iniciando...",
                          font=('Segoe UI', 11, 'bold'),
                          bg=C['bg_card'], fg=C['text_primary'],
                          anchor='w', wraplength=350, justify='left')
        status.pack(anchor='w', pady=(4, 2))
        cls._status_label_ref = status

        detail = tk.Label(info, text="",
                          font=('Consolas', 8),
                          bg=C['bg_card'], fg=C['text_secondary'],
                          anchor='w', wraplength=350, justify='left')
        detail.pack(anchor='w')
        cls._detail_label_ref = detail

        # Dots de fase (#11)
        dots_row = tk.Frame(info, bg=C['bg_card'])
        dots_row.pack(anchor='w', pady=(6, 0))
        dots_c = tk.Canvas(dots_row, width=120, height=10,
                           bg=C['bg_card'], highlightthickness=0, bd=0)
        dots_c.pack(anchor='w')
        cls._phase_dots_canvas = dots_c

        def _draw_dots(pct_val=0):
            dots_c.delete('all')
            n = 10
            filled = int((pct_val / 100.0) * n)
            for i in range(n):
                x0, y0 = i * 12 + 2, 3
                col = C['accent_light'] if i < filled else C['border_bright']
                dots_c.create_oval(x0, y0, x0 + 6, y0 + 6, fill=col, outline='')

        dots_c._draw_dots = _draw_dots
        _draw_dots(0)

        # ── Progress bar con shimmer ────────────────────────────────────────
        bar_wrap = tk.Frame(card, bg=C['border'], height=4)
        bar_wrap.pack(fill=tk.X, padx=12, pady=(14, 0))
        bar_wrap.pack_propagate(False)
        bar_c = tk.Canvas(bar_wrap, height=4,
                          bg=C['bg_secondary'], highlightthickness=0, bd=0)
        bar_c.pack(fill=tk.BOTH, expand=True)

        bar_c._shimmer_x = 0

        def _draw_bar(pct_val):
            bar_c.delete('bar')
            w = bar_c.winfo_width()
            if w < 2:
                return
            fw = max(0, int(w * pct_val / 100))
            if fw > 0:
                # Gradiente segmentado cobre
                segments = 30
                seg_w = max(1, fw // segments)
                for i in range(0, fw, seg_w):
                    t = (i + seg_w / 2) / max(1, fw)
                    if t < 0.5:
                        # accent_deep -> accent
                        r1, g1, b1 = 0x6B, 0x3A, 0x1D
                        r2, g2, b2 = 0xB8, 0x73, 0x33
                        tt = t / 0.5
                    else:
                        # accent -> accent_glow
                        r1, g1, b1 = 0xB8, 0x73, 0x33
                        r2, g2, b2 = 0xFF, 0xC8, 0x99
                        tt = (t - 0.5) / 0.5
                    rr = int(r1 + (r2 - r1) * tt)
                    gg = int(g1 + (g2 - g1) * tt)
                    bb = int(b1 + (b2 - b1) * tt)
                    color = f'#{rr:02x}{gg:02x}{bb:02x}'
                    bar_c.create_rectangle(i, 0, min(i + seg_w, fw), 4,
                                           fill=color, outline='', tags='bar')

                # Punta brillante a la derecha
                tip_w = min(8, fw)
                if tip_w > 0:
                    bar_c.create_rectangle(fw - tip_w, 0, fw, 4,
                                           fill=C['accent_light'], outline='', tags='bar')
                    bar_c.create_rectangle(fw - 1, 0, fw, 4,
                                           fill='#FFFFFF', outline='', tags='bar')

                # Shimmer "scan-line" que se desliza sobre el fill
                shimmer_w = 30
                bar_c._shimmer_x = (bar_c._shimmer_x + 4) % max(1, fw + shimmer_w)
                sx = bar_c._shimmer_x - shimmer_w
                if sx < fw and sx + shimmer_w > 0:
                    sx0 = max(0, sx)
                    sx1 = min(fw, sx + shimmer_w)
                    # Banda con stipple para suavizar
                    bar_c.create_rectangle(sx0, 0, sx1, 4,
                                           fill='#FFFFFF', outline='',
                                           stipple='gray25', tags='bar')

        bar_c._draw = _draw_bar

        if not (getattr(cls, '_ui_prefs', None) or {}).get('ui_reduced_motion'):
            def _shimmer_tick():
                try:
                    _draw_bar(cls._ring_pct)
                    bar_c.after(80, _shimmer_tick)
                except Exception:
                    pass
            bar_c.after(150, _shimmer_tick)

        # ── Bottom row: timer + resources ───────────────────────────────────
        bot = tk.Frame(card, bg=C['bg_card'])
        bot.pack(fill=tk.X, padx=12, pady=(10, 0))

        timer = tk.Label(bot, text="Tiempo 00:00:00",
                         font=('Consolas', 9),
                         bg=C['bg_card'], fg=C['text_secondary'])
        timer.pack(side=tk.LEFT)

        res_wrap = tk.Frame(bot, bg=C['bg_card'])
        res_wrap.pack(side=tk.RIGHT)
        resources = tk.Label(res_wrap, text="",
                             font=('Segoe UI', 7),
                             bg=C['bg_card'], fg=C['text_secondary'])
        resources.pack(anchor='e')
        meters = tk.Frame(res_wrap, bg=C['bg_card'])
        meters.pack(anchor='e', pady=(2, 0))
        cls._cpu_bar_canvas = tk.Canvas(meters, width=70, height=4,
                                        bg=C['bg_secondary'], highlightthickness=0, bd=0)
        cls._cpu_bar_canvas.pack(anchor='e')
        cls._ram_bar_canvas = tk.Canvas(meters, width=70, height=4,
                                        bg=C['bg_secondary'], highlightthickness=0, bd=0)
        cls._ram_bar_canvas.pack(anchor='e', pady=(2, 0))

        # Contadores en vivo (#13)
        counts_row = tk.Frame(card, bg=C['bg_card'])
        counts_row.pack(fill=tk.X, padx=12, pady=(8, 0))
        cls._counter_labels = {}
        _chip_specs = (
            ('critical', 'CRIT', C['red']),
            ('suspicious', 'SOSP', C['amber']),
            ('low', 'BAJO', C['blue']),
            ('clean', 'OK', C['green']),
        )
        for key, short, color in _chip_specs:
            chip_fr = tk.Frame(counts_row, bg=C['border_bright'], padx=1, pady=1)
            chip_fr.pack(side=tk.LEFT, padx=(0, 6))
            chip = tk.Label(
                chip_fr,
                text=f"{short}: 0",
                font=('Segoe UI', 7, 'bold'),
                bg=C['bg_secondary'],
                fg=color,
                padx=8,
                pady=2,
            )
            chip.pack()
            cls._counter_labels[key] = chip

        # Risk meter (#15 #32 #33)
        risk_row = tk.Frame(card, bg=C['bg_card'])
        risk_row.pack(fill=tk.X, padx=12, pady=(6, 4))
        cls._risk_label = tk.Label(
            risk_row, text="Riesgo —",
            font=('Segoe UI', 7),
            bg=C['bg_card'], fg=C['text_muted'],
        )
        cls._risk_label.pack(side=tk.LEFT)
        cls._risk_canvas = tk.Canvas(risk_row, height=6, bg=C['bg_secondary'],
                                     highlightthickness=0, bd=0)
        cls._risk_canvas.pack(side=tk.LEFT, fill=tk.X, expand=True, padx=(8, 0))
        try:
            if not getattr(cls, '_ui_enh_patch', False):
                from ui_enhancements import patch_modern_ui
                patch_modern_ui(cls)
                cls._ui_enh_patch = True
            sp = cls.create_sparkline(risk_row)
            sp.pack(side=tk.RIGHT, padx=(8, 0))
            cls.attach_files_counter(card)
            cls.create_phase_sidebar(parent)
            cls.add_chip_tooltips(getattr(cls, '_counter_labels', {}))
        except Exception:
            pass

        tk.Label(
            card, text="Argus Projects",
            font=('Segoe UI', 6),
            bg=C['bg_card'], fg=C['border_bright'],
        ).pack(anchor='e', padx=12, pady=(0, 6))

        # compat: hidden ttk bar y pct label
        pb = ttk.Progressbar(card, mode='determinate', maximum=100,
                             style='Argus.Horizontal.TProgressbar')
        pct_lbl = tk.Label(card, text="0%", font=cls.FONTS['big_pct'],
                           bg=C['bg_card'], fg=C['bg_card'])

        cancel_row = tk.Frame(card, bg=C['bg_card'])
        cancel_row.pack(fill=tk.X, pady=(6, 0))
        cancel_btn = tk.Button(
            cancel_row,
            text="✕  Cancelar escaneo",
            font=('Segoe UI', 8),
            bg=C['bg_card'],
            fg=C['text_muted'],
            activebackground=C['bg_hover'],
            activeforeground=C['red'],
            relief=tk.FLAT,
            bd=0,
            cursor='hand2',
            padx=10,
            pady=4,
            highlightthickness=1,
            highlightbackground=C['border'],
            highlightcolor=C['accent'],
        )
        cancel_btn.pack(anchor='e', padx=12, pady=(0, 8))
        cancel_btn.bind('<Enter>', lambda _e: cancel_btn.config(highlightbackground=C['accent']))
        cancel_btn.bind('<Leave>', lambda _e: cancel_btn.config(highlightbackground=C['border']))

        return {
            'container':  outer,
            'card':       card,
            'status':     status,
            'progress':   pb,
            'detail':     detail,
            'timer':      timer,
            'resources':  resources,
            'percent':    pct_lbl,
            '_canvas':    bar_c,
            '_ring':      ring_c,
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

        card = tk.Frame(outer, bg=C['bg_card'],
                        highlightbackground=C['border_bright'],
                        highlightthickness=1)
        card.pack(fill=tk.BOTH, expand=True)

        center = tk.Frame(card, bg=C['bg_card'])
        center.place(relx=0.5, rely=0.5, anchor='center')

        icon_c = tk.Canvas(center, width=56, height=56,
                           bg=C['bg_card'], highlightthickness=0)
        icon_c.pack(pady=(0, 14))
        # Icon idle: circulo cobre suave
        icon_c.create_oval(2, 2, 54, 54,
                           outline=C['accent_deep'], width=1.4,
                           fill=C['bg_card'])
        icon_c.create_oval(6, 6, 50, 50,
                           outline=C['accent'], width=1.0,
                           fill='')

        main_lbl = tk.Label(center,
                            text="Esperando inicio",
                            font=('Segoe UI', 13, 'bold'),
                            bg=C['bg_card'], fg=C['text_secondary'])
        main_lbl.pack()

        sub_lbl = tk.Label(center, text="",
                           font=('Segoe UI', 8),
                           bg=C['bg_card'], fg=C['text_muted'])
        sub_lbl.pack(pady=(4, 0))

        top_find = tk.Label(center, text="",
                            font=('Consolas', 7),
                            bg=C['bg_card'], fg=C['accent_light'],
                            wraplength=320, justify='center')
        top_find.pack(pady=(6, 0))
        cls._top_finding_label = top_find

        outer.pack_forget()

        widgets = {
            'outer':       outer,
            'card':        card,
            'icon_canvas': icon_c,
            'main_label':  main_lbl,
            'sub_label':   sub_lbl,
            'top_finding': top_find,
        }
        try:
            if not getattr(cls, '_ui_enh_patch', False):
                from ui_enhancements import patch_modern_ui
                patch_modern_ui(cls)
                cls._ui_enh_patch = True
            cls.enhance_completion_panel(widgets)
        except Exception:
            pass
        return widgets

    @classmethod
    def show_completion_panel(cls, completion_widgets, visible: bool = True):
        outer = (completion_widgets or {}).get('outer')
        if outer is None:
            return
        try:
            if visible:
                outer.pack(fill=tk.BOTH, expand=True, padx=24, pady=(4, 10))
            else:
                outer.pack_forget()
        except Exception:
            pass

    @classmethod
    def set_scan_ui_mode(cls, progress_widgets=None, completion_widgets=None, scanning: bool = True):
        """Durante el scan: barra visible; al terminar: panel de completado."""
        if progress_widgets:
            cont = progress_widgets.get('container')
            if cont is not None:
                try:
                    if scanning:
                        cont.pack(fill=tk.BOTH, expand=True, padx=24, pady=(14, 6))
                    else:
                        cont.pack_forget()
                except Exception:
                    pass
        cls.show_completion_panel(completion_widgets, visible=not scanning)

    # ══════════════════════════════════════════════════════════════════════
    #  BUTTON con shimmer al hover
    # ══════════════════════════════════════════════════════════════════════
    @classmethod
    def create_button(cls, parent, text, command, style='primary', icon=''):
        C = cls.COLORS
        label = f"{icon}  {text}" if icon else text

        if style == 'primary':
            bg = C['accent'];        hv = C['accent_hover']
            fg = '#FFFFFF';          px, py, fs = 28, 11, 10
        elif style == 'secondary':
            bg = C['bg_card'];       hv = C['bg_hover']
            fg = C['text_primary'];  px, py, fs = 18, 8, 9
        else:
            bg = C['bg_secondary'];  hv = C['bg_card']
            fg = C['text_secondary'];px, py, fs = 14, 6, 8

        frame = tk.Frame(parent, bg=C['bg_primary'])
        btn = tk.Button(
            frame, text=label, command=command,
            bg=bg, fg=fg,
            font=('Segoe UI', fs, 'bold'),
            padx=px, pady=py,
            relief=tk.FLAT, bd=0, cursor='hand2',
            activebackground=hv, activeforeground=fg,
            highlightthickness=0,
        )
        btn.pack(fill=tk.X)

        # Hover: gradient color sweep (5 frames)
        def _hover_in(_e=None):
            try:
                btn.config(bg=hv)
            except Exception:
                pass

        def _hover_out(_e=None):
            try:
                btn.config(bg=bg)
            except Exception:
                pass

        btn.bind('<Enter>', _hover_in)
        btn.bind('<Leave>', _hover_out)
        return frame

    # ══════════════════════════════════════════════════════════════════════
    #  RESULTS SECTION (oculto por defecto)
    # ══════════════════════════════════════════════════════════════════════
    @classmethod
    def create_results_section(cls, parent):
        C = cls.COLORS
        hidden = tk.Frame(parent, bg=C['bg_primary'], height=0)
        hidden.pack()
        hidden.pack_propagate(False)

        ta = scrolledtext.ScrolledText(
            hidden, wrap=tk.WORD,
            font=cls.FONTS['mono'],
            bg=C['bg_card'], fg=C['text_primary'],
            relief=tk.FLAT, bd=0,
        )
        ta.pack(fill=tk.BOTH, expand=True)

        for tag, color in [('success', C['green']), ('warning', C['amber']),
                            ('danger', C['red']),   ('info',    C['blue']),
                            ('header', C['text_primary']), ('muted', C['text_secondary']),
                            ('accent', C['accent'])]:
            ta.tag_config(tag, foreground=color)

        title = tk.Label(hidden, text='', bg=C['bg_primary'])
        return {'container': hidden, 'text': ta, 'title': title}

    # ══════════════════════════════════════════════════════════════════════
    #  PUBLIC HELPERS
    # ══════════════════════════════════════════════════════════════════════
    @classmethod
    def format_phase_label(cls, text: str, max_len: int = 52) -> str:
        """Recorta fases largas para que no rompan el layout de la ventana."""
        if not text:
            return ""
        one_line = " ".join(str(text).split())
        if len(one_line) <= max_len:
            return one_line
        return one_line[: max_len - 1] + "\u2026"

    @classmethod
    def set_status_badge(cls, text, color=None):
        if cls._status_badge is None:
            return
        col = color or cls.COLORS['accent']
        try:
            up = (text or '').upper()
            if 'LISTO' in up or 'OK' in up:
                icon = '✓'
            elif 'ESCANE' in up:
                icon = '◉'
            elif 'ERROR' in up or 'CANCEL' in up:
                icon = '✕'
            else:
                icon = '●'
            cls._status_badge.config(text=f"{icon}  {text}", fg=col)
            if text and 'ESCANE' in text.upper():
                cls._start_badge_pulse(col)
            else:
                cls._stop_badge_pulse()
        except Exception:
            pass

    _badge_pulse_after = None
    _badge_pulse_state = 0

    @classmethod
    def _start_badge_pulse(cls, base_color):
        if cls._status_badge is None:
            return
        cls._stop_badge_pulse()
        try:
            base_text = cls._status_badge.cget('text') or '●  ESCANEANDO'
            txt_only = base_text.split('  ', 1)[-1] if '  ' in base_text else base_text

            try:
                r, g, b = int(base_color[1:3], 16), int(base_color[3:5], 16), int(base_color[5:7], 16)
            except Exception:
                r, g, b = 0xB8, 0x73, 0x33
            dim = f'#{int(r*0.5):02x}{int(g*0.5):02x}{int(b*0.5):02x}'

            def _tick():
                if cls._status_badge is None:
                    return
                try:
                    cls._badge_pulse_state = (cls._badge_pulse_state + 1) % 4
                    # 4 estados para una onda mas fluida
                    phase = cls._badge_pulse_state
                    if phase == 0:
                        color_now = base_color
                    elif phase == 1:
                        # Mezcla 75% base + 25% dim
                        color_now = base_color
                    elif phase == 2:
                        color_now = dim
                    else:
                        color_now = dim
                    cls._status_badge.config(text=f"●  {txt_only}", fg=color_now)
                    cls._badge_pulse_after = cls._status_badge.after(450, _tick)
                except Exception:
                    pass
            _tick()
        except Exception:
            pass

    @classmethod
    def _stop_badge_pulse(cls):
        try:
            if cls._badge_pulse_after and cls._status_badge is not None:
                cls._status_badge.after_cancel(cls._badge_pulse_after)
        except Exception:
            pass
        cls._badge_pulse_after = None

    _counter_short = {'critical': 'CRIT', 'suspicious': 'SOSP', 'low': 'BAJO', 'clean': 'OK'}

    @classmethod
    def update_counter(cls, key, value):
        lbl = getattr(cls, '_counter_labels', {}).get(key)
        if lbl is None:
            return
        short = cls._counter_short.get(key, key.upper()[:4])
        try:
            v = int(value)
            prev = cls._counter_prev.get(key, 0)
            lbl.config(text=f"{short}: {v}")
            if v > prev:
                try:
                    lbl.config(bg=cls.COLORS['bg_hover'])
                    lbl.after(120, lambda: lbl.config(bg=cls.COLORS['bg_secondary']))
                except Exception:
                    pass
            cls._counter_prev[key] = v
        except Exception:
            pass

    @classmethod
    def update_phase_dots(cls, pct: float):
        if cls._phase_dots_canvas and hasattr(cls._phase_dots_canvas, '_draw_dots'):
            try:
                cls._phase_dots_canvas._draw_dots(float(pct))
            except Exception:
                pass

    @classmethod
    def update_status_fade(cls, status_text=None, detail_text=None):
        """Fade suave al cambiar mensajes (#12)."""
        cls._detail_fade_gen += 1
        gen = cls._detail_fade_gen
        C = cls.COLORS

        def _step(alpha, st=None, dt=None):
            if gen != cls._detail_fade_gen:
                return
            try:
                if st is not None and cls._status_label_ref:
                    fg = C['text_primary'] if alpha > 0.5 else C['text_muted']
                    cls._status_label_ref.config(text=st, fg=fg)
                if dt is not None and cls._detail_label_ref:
                    cls._detail_label_ref.config(
                        text=dt,
                        fg=C['text_secondary'] if alpha > 0.5 else C['text_muted'],
                    )
            except Exception:
                pass
            if alpha < 1.0 and cls._root_ref:
                cls._root_ref.after(30, lambda: _step(min(1.0, alpha + 0.25), st, dt))

        if status_text is not None or detail_text is not None:
            _step(0.0, status_text, detail_text)
        if detail_text:
            try:
                cls.append_phase_history(detail_text)
            except Exception:
                pass

    @classmethod
    def update_risk_meter(cls, score: int, crit_count: int = 0):
        """Barra de riesgo 0-100 (#15)."""
        if cls._risk_canvas is None:
            return
        C = cls.COLORS
        score = max(0, min(100, int(score)))
        try:
            if cls._risk_label:
                cls._risk_label.config(text=f"Riesgo {score}/100", font=('Segoe UI', 9, 'bold'))
            try:
                cls.push_risk_sample(score)
            except Exception:
                pass
            cls._risk_canvas.delete('all')
            w = cls._risk_canvas.winfo_width()
            if w < 8:
                w = 200
            fw = int(w * score / 100)
            fill = C['green'] if score < 35 else (C['amber'] if score < 65 else C['red'])
            if crit_count > 0:
                fill = C['red_deep']
            cls._risk_canvas.create_rectangle(0, 0, w, 6, fill=C['bg_secondary'], outline='')
            if fw > 0:
                cls._risk_canvas.create_rectangle(0, 0, fw, 6, fill=fill, outline='')
        except Exception:
            pass

    @classmethod
    def update_resource_meters(cls, cpu_pct=None, ram_pct=None):
        """Mini barras CPU/RAM (#16)."""
        C = cls.COLORS

        def _draw(canvas, pct, label):
            if canvas is None or pct is None:
                return
            try:
                canvas.delete('all')
                w = 70
                fw = int(w * max(0, min(100, float(pct))) / 100)
                canvas.create_rectangle(0, 0, w, 4, fill=C['bg_secondary'], outline='')
                if fw > 0:
                    canvas.create_rectangle(0, 0, fw, 4, fill=C['accent'], outline='')
            except Exception:
                pass

        _draw(cls._cpu_bar_canvas, cpu_pct, 'CPU')
        _draw(cls._ram_bar_canvas, ram_pct, 'RAM')

    @classmethod
    def set_top_finding(cls, completion_widgets, text: str):
        lbl = (completion_widgets or {}).get('top_finding') or cls._top_finding_label
        if lbl is None:
            return
        try:
            lbl.config(text=text[:120] if text else '')
        except Exception:
            pass

    @classmethod
    def _trigger_confetti(cls, canvas):
        """Partículas cobre al completar (#20)."""
        if canvas is None:
            return
        C = cls.COLORS
        particles = []
        for _ in range(18):
            particles.append({
                'x': random.randint(8, 48),
                'y': random.randint(8, 48),
                'vy': random.uniform(-2.5, -0.5),
                'vx': random.uniform(-1.2, 1.2),
                'life': random.randint(8, 20),
            })

        def _tick():
            try:
                canvas.delete('conf')
                alive = False
                for p in particles:
                    if p['life'] <= 0:
                        continue
                    alive = True
                    p['life'] -= 1
                    p['x'] += p['vx']
                    p['y'] += p['vy']
                    p['vy'] += 0.15
                    canvas.create_oval(
                        p['x'], p['y'], p['x'] + 3, p['y'] + 3,
                        fill=C['accent_light'], outline='', tags='conf',
                    )
                if alive:
                    canvas.after(40, _tick)
            except Exception:
                pass
        _tick()

    @classmethod
    def update_canvas_bar(cls, canvas, pct_val):
        """Actualiza barra y ring. Aplica tween numerico para que el numero
        del ring no salte en seco entre valores."""
        try:
            cls.update_phase_dots(float(pct_val))
            cls._ring_target_pct = float(pct_val)
            # Si la diferencia es grande (>2%), tweenamos suavemente
            if cls._ring_canvas and abs(cls._ring_target_pct - cls._ring_pct) > 0.5:
                cls._start_pct_tween()
            else:
                cls._ring_pct = float(pct_val)
            if hasattr(canvas, '_draw'):
                canvas._draw(pct_val)
        except Exception:
            pass

    _pct_tween_after = None

    @classmethod
    def _start_pct_tween(cls):
        try:
            if cls._pct_tween_after is not None:
                return  # ya hay un tween corriendo

            def _step():
                try:
                    diff = cls._ring_target_pct - cls._ring_pct
                    if abs(diff) < 0.3:
                        cls._ring_pct = cls._ring_target_pct
                        cls._pct_tween_after = None
                        return
                    # Easing exponencial: avanza 22% por frame
                    cls._ring_pct += diff * 0.22
                    cls._pct_tween_after = cls._ring_canvas.after(30, _step)
                except Exception:
                    cls._pct_tween_after = None
            _step()
        except Exception:
            cls._pct_tween_after = None

    @classmethod
    def set_completion_state(cls, completion_widgets, success=True, message=None, sub=None, counts=None):
        C = cls.COLORS
        icon_c   = completion_widgets.get('icon_canvas')
        main_lbl = completion_widgets.get('main_label')
        sub_lbl  = completion_widgets.get('sub_label')

        if icon_c:
            icon_c.delete('all')
            color = C['green_glow'] if success else C['red_deep']
            color_dim = C['green'] if success else C['red']
            color_glow = C['green_glow'] if success else C['red']
            bg    = C['bg_card']

            # Halo radial cobre/verde/rojo (anillos concentricos)
            icon_c.create_oval(0, 0, 56, 56, outline=color_dim, width=1, fill=bg)
            icon_c.create_oval(3, 3, 53, 53, outline=color, width=1.5, fill=bg)
            icon_c.create_oval(6, 6, 50, 50, outline=color_glow, width=1, fill='')
            icon_c.create_oval(10, 10, 46, 46, outline=color_dim, width=0.8, fill='')

            if success:
                # Sombra del check
                icon_c.create_line(17, 28, 25, 38, 39, 18,
                                   fill=color_dim, width=3,
                                   joinstyle='round', capstyle='round')
                # Check principal
                icon_c.create_line(16, 27, 24, 37, 38, 17,
                                   fill=color, width=2.5,
                                   joinstyle='round', capstyle='round')
                # Highlight
                icon_c.create_line(20, 31, 24, 35, 30, 24,
                                   fill='#FFFFFF', width=1,
                                   joinstyle='round', capstyle='round')
            else:
                icon_c.create_line(17, 17, 39, 39, fill=color, width=2.5, capstyle='round')
                icon_c.create_line(39, 17, 17, 39, fill=color, width=2.5, capstyle='round')

        if main_lbl:
            txt = message or ("Escaneo completado" if success else "Error en el escaneo")
            main_lbl.config(text=txt, fg=C['green_glow'] if success else C['red_deep'])

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
                line = " · ".join(parts)
                if sub:
                    line = f"{line} — {sub}"
                sub_lbl.config(text=line, fg=C['text_secondary'])
            else:
                sub_lbl.config(text=sub or "", fg=C['text_secondary'])

        if success and icon_c:
            cls._trigger_confetti(icon_c)
        try:
            crit_n = int((counts or {}).get('critical', 0))
            cls.flash_dwm_border(success and crit_n == 0)
            if success:
                cls.play_complete_sound()
        except Exception:
            pass
