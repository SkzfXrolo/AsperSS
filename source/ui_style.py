import tkinter as tk
from tkinter import ttk, scrolledtext
import os
import sys
import math
import ctypes

try:
    from PIL import Image, ImageTk
    _PIL_OK = True
except ImportError:
    _PIL_OK = False


class ModernUI:
    """Argus Scanner — Echo-inspired UI. Dark, red accent, minimal."""

    COLORS = {
        'bg_primary':   '#0A0A0C',
        'bg_secondary': '#101013',
        'bg_card':      '#16161A',
        'bg_hover':     '#1C1C22',

        'text_primary':   '#F5F2F4',
        'text_secondary': '#7A7580',
        'text_muted':     '#3A3640',

        'accent':       '#E53E3E',
        'accent_light': '#FC8181',
        'accent_hover': '#C53030',
        'accent_deep':  '#7A1722',
        'accent_glow':  '#FF5050',
        'green':        '#48BB78',
        'green_glow':   '#5DD08C',
        'amber':        '#ECC94B',
        'red':          '#FC5555',
        'blue':         '#63B3ED',
        'gold':         '#B8860B',

        'border':       '#1E1E24',
        'border_bright':'#2A2A30',
        'separator':    '#181820',
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
    _ring_canvas   = None
    _ring_after_id = None

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

    # ── window ────────────────────────────────────────────────────────────────
    @staticmethod
    def apply_window_style(root):
        root.title("Argus Scanner")
        w, h = 705, 279
        x = (root.winfo_screenwidth()  - w) // 2
        y = (root.winfo_screenheight() - h) // 2
        root.geometry(f"{w}x{h}+{x}+{y}")
        root.resizable(False, False)
        root.overrideredirect(True)
        root.configure(bg=ModernUI.COLORS['bg_primary'])
        base = ModernUI._base_path()

        # Ícono — intentar .ico primero, luego .png
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

        # Aplicar estilos DWM/GDI después de que la ventana tenga HWND
        root.update_idletasks()
        try:
            hwnd = ctypes.windll.user32.GetParent(root.winfo_id())
            if not hwnd:
                hwnd = root.winfo_id()

            # 1. Mostrar en barra de tareas: quitar WS_EX_TOOLWINDOW, poner WS_EX_APPWINDOW
            GWL_EXSTYLE      = -20
            WS_EX_APPWINDOW  = 0x00040000
            WS_EX_TOOLWINDOW = 0x00000080
            style = ctypes.windll.user32.GetWindowLongW(hwnd, GWL_EXSTYLE)
            style = (style & ~WS_EX_TOOLWINDOW) | WS_EX_APPWINDOW
            ctypes.windll.user32.SetWindowLongW(hwnd, GWL_EXSTYLE, style)
            root.withdraw()
            root.after(15, root.deiconify)

            # 2. Esquinas redondeadas — Win 10/11 compatible via SetWindowRgn + CreateRoundRectRgn
            #    (DWMWA_WINDOW_CORNER_PREFERENCE=33 solo funciona en Win 11 build 22000+)
            RADIUS = 16
            w = root.winfo_width()  or 705
            h = root.winfo_height() or 279
            hrgn = ctypes.windll.gdi32.CreateRoundRectRgn(0, 0, w + 1, h + 1, RADIUS * 2, RADIUS * 2)
            if hrgn:
                ctypes.windll.user32.SetWindowRgn(hwnd, hrgn, True)

            # Intentar también via DWM por si es Win 11
            try:
                pref = ctypes.c_int(2)  # DWMWCP_ROUND
                ctypes.windll.dwmapi.DwmSetWindowAttribute(hwnd, 33, ctypes.byref(pref), ctypes.sizeof(pref))
            except Exception:
                pass

            # 3. Borde rojo via DWM (Win 11) — en Win 10 no tiene efecto pero no falla
            try:
                red_colorref = ctypes.c_int(0x003E3EE5)  # #E53E3E en COLORREF BGR
                ctypes.windll.dwmapi.DwmSetWindowAttribute(hwnd, 34, ctypes.byref(red_colorref), ctypes.sizeof(red_colorref))
            except Exception:
                pass

        except Exception:
            pass

        def _apply_rounded_rgn():
            """Re-aplica la región redondeada cuando la ventana ya tiene tamaño real."""
            try:
                _hwnd = ctypes.windll.user32.GetParent(root.winfo_id()) or root.winfo_id()
                _w = root.winfo_width()
                _h = root.winfo_height()
                if _w > 1 and _h > 1:
                    _hrgn = ctypes.windll.gdi32.CreateRoundRectRgn(0, 0, _w + 1, _h + 1, 32, 32)
                    if _hrgn:
                        ctypes.windll.user32.SetWindowRgn(_hwnd, _hrgn, True)
            except Exception:
                pass
        # Aplicar de nuevo tras 80ms cuando tkinter ya conoce el tamaño real
        root.after(80, _apply_rounded_rgn)

    @staticmethod
    def _base_path():
        if getattr(sys, 'frozen', False):
            return sys._MEIPASS
        return os.path.dirname(os.path.abspath(__file__))

    # ── header ────────────────────────────────────────────────────────────────
    @classmethod
    def create_header(cls, parent):
        C = cls.COLORS

        hdr = tk.Frame(parent, bg=C['bg_primary'])
        hdr.pack(fill=tk.X)

        inner = tk.Frame(hdr, bg=C['bg_primary'])
        inner.pack(fill=tk.X, padx=24, pady=(12, 10))

        # Left: logo + brand
        left = tk.Frame(inner, bg=C['bg_primary'])
        left.pack(side=tk.LEFT, fill=tk.Y)

        # Logo image (24×24); fallback to canvas shield
        _logo_shown = False
        try:
            logo_path = os.path.join(cls._base_path(), 'assets', 'logo.png')
            if os.path.exists(logo_path) and _PIL_OK:
                _raw = Image.open(logo_path).resize((24, 24), Image.LANCZOS)
                _photo = ImageTk.PhotoImage(_raw)
                logo_lbl = tk.Label(left, image=_photo,
                                    bg=C['bg_primary'], bd=0)
                logo_lbl.image = _photo  # evitar GC
                logo_lbl.pack(side=tk.LEFT, padx=(0, 8))
                _logo_shown = True
        except Exception:
            pass

        if not _logo_shown:
            ic = tk.Canvas(left, width=22, height=22,
                           bg=C['bg_primary'], highlightthickness=0)
            ic.pack(side=tk.LEFT, padx=(0, 8))
            ic.create_polygon(11, 2, 3, 6, 3, 13, 11, 20, 19, 13, 19, 6,
                              fill='', outline=C['accent'], width=1.5)
            ic.create_line(7, 11, 10, 14, 15, 8,
                           fill=C['accent'], width=1.5,
                           joinstyle='round', capstyle='round')

        brand = tk.Frame(left, bg=C['bg_primary'])
        brand.pack(side=tk.LEFT)
        tk.Label(brand, text="ARGUS SCANNER",
                 font=('Segoe UI', 10, 'bold'),
                 bg=C['bg_primary'], fg=C['text_primary'],
                 anchor='w').pack(anchor='w')
        tk.Label(brand, text="by Argus Projects",
                 font=('Segoe UI', 7),
                 bg=C['bg_primary'], fg=C['text_muted'],
                 anchor='w').pack(anchor='w')

        # Right: live status badge
        right = tk.Frame(inner, bg=C['bg_primary'])
        right.pack(side=tk.RIGHT, fill=tk.Y)

        badge_bg = tk.Frame(right, bg=C['bg_card'],
                            highlightbackground=C['border_bright'],
                            highlightthickness=1)
        badge_bg.pack(side=tk.RIGHT, pady=2)
        badge = tk.Label(badge_bg,
                         text="●  LISTO",
                         font=('Segoe UI', 7, 'bold'),
                         bg=C['bg_card'], fg=C['green'],
                         padx=10, pady=5)
        badge.pack()
        cls._status_badge = badge

        # Bottom separator line (red accent)
        tk.Frame(hdr, bg=C['accent'], height=1).pack(fill=tk.X)
        return hdr

    # ── progress section ──────────────────────────────────────────────────────
    @classmethod
    def create_progress_section(cls, parent):
        cls._apply_ttk_style()
        C = cls.COLORS

        outer = tk.Frame(parent, bg=C['bg_primary'])
        outer.pack(fill=tk.BOTH, expand=True, padx=24, pady=(14, 6))

        # ── Top row: big percentage + animated ring ───────────────────────────
        top = tk.Frame(outer, bg=C['bg_primary'])
        top.pack(fill=tk.X)

        # Left: ring + percent
        ring_wrap = tk.Frame(top, bg=C['bg_primary'])
        ring_wrap.pack(side=tk.LEFT)

        ring_size = 110
        ring_c = tk.Canvas(ring_wrap, width=ring_size, height=ring_size,
                           bg=C['bg_primary'], highlightthickness=0)
        ring_c.pack()
        cls._ring_canvas = ring_c
        cls._ring_pct    = 0

        def _interp_color(c1, c2, t):
            """Interpolación lineal entre dos colores hex."""
            try:
                r1, g1, b1 = int(c1[1:3], 16), int(c1[3:5], 16), int(c1[5:7], 16)
                r2, g2, b2 = int(c2[1:3], 16), int(c2[3:5], 16), int(c2[5:7], 16)
                r = int(r1 + (r2 - r1) * t)
                g = int(g1 + (g2 - g1) * t)
                b = int(b1 + (b2 - b1) * t)
                return f'#{r:02x}{g:02x}{b:02x}'
            except Exception:
                return c1

        def _draw_ring(pct):
            ring_c.delete('all')
            pad = 10
            x0, y0 = pad, pad
            x1, y1 = ring_size - pad, ring_size - pad

            # Halo exterior sutil (capa 1)
            ring_c.create_arc(x0 - 3, y0 - 3, x1 + 3, y1 + 3,
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

            # Progress arc — degradado por segmentos (rojo → amarillo→verde según pct)
            if pct > 0:
                # Color según progreso: profundo en bajo, brillante en alto
                if pct < 50:
                    arc_color = _interp_color(C['accent_deep'], C['accent'], pct / 50)
                else:
                    arc_color = _interp_color(C['accent'], C['accent_glow'], (pct - 50) / 50)

                # Glow exterior (más ancho, color tenue)
                extent_full = -int(360 * pct / 100)
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
                # Punta brillante (último 8% del arco)
                if pct > 5:
                    tip_extent = max(-30, int(-360 * 0.08))
                    tip_start  = 90 + extent_full - tip_extent
                    ring_c.create_arc(x0, y0, x1, y1,
                                      start=tip_start, extent=tip_extent,
                                      style='arc',
                                      outline=C['accent_light'],
                                      width=6)

            # Texto del porcentaje (sombra + main)
            cx, cy = ring_size // 2, ring_size // 2
            ring_c.create_text(cx + 1, cy + 1,
                               text=f"{int(pct)}%",
                               font=('Segoe UI', 18, 'bold'),
                               fill=C['bg_primary'])
            ring_c.create_text(cx, cy,
                               text=f"{int(pct)}%",
                               font=('Segoe UI', 18, 'bold'),
                               fill=C['text_primary'])

        ring_c._draw = _draw_ring
        _draw_ring(0)

        # Right: info block
        info = tk.Frame(top, bg=C['bg_primary'])
        info.pack(side=tk.LEFT, fill=tk.BOTH, expand=True, padx=(20, 0))

        tk.Label(info, text="ANÁLISIS EN CURSO",
                 font=('Segoe UI', 7, 'bold'),
                 bg=C['bg_primary'], fg=C['text_muted'],
                 anchor='w').pack(anchor='w')

        status = tk.Label(info, text="Iniciando...",
                          font=('Segoe UI', 11, 'bold'),
                          bg=C['bg_primary'], fg=C['text_primary'],
                          anchor='w', wraplength=350, justify='left')
        status.pack(anchor='w', pady=(4, 6))

        detail = tk.Label(info, text="",
                          font=('Consolas', 8),
                          bg=C['bg_primary'], fg=C['text_secondary'],
                          anchor='w', wraplength=350, justify='left')
        detail.pack(anchor='w')

        # ── Progress bar ──────────────────────────────────────────────────────
        bar_wrap = tk.Frame(outer, bg=C['border'], height=4)
        bar_wrap.pack(fill=tk.X, pady=(18, 0))
        bar_wrap.pack_propagate(False)
        bar_c = tk.Canvas(bar_wrap, height=4,
                          bg=C['bg_secondary'], highlightthickness=0, bd=0)
        bar_c.pack(fill=tk.BOTH, expand=True)

        def _draw_bar(pct_val):
            bar_c.delete('bar')
            w = bar_c.winfo_width()
            if w < 2:
                return
            fw = max(0, int(w * pct_val / 100))
            if fw > 0:
                # Degradado simulado por segmentos verticales
                # de accent_deep → accent → accent_glow
                segments = 30
                seg_w = max(1, fw // segments)
                for i in range(0, fw, seg_w):
                    t = (i + seg_w / 2) / max(1, fw)
                    if t < 0.5:
                        # accent_deep -> accent
                        r1, g1, b1 = 0x7A, 0x17, 0x22
                        r2, g2, b2 = 0xE5, 0x3E, 0x3E
                        tt = t / 0.5
                    else:
                        # accent -> accent_glow
                        r1, g1, b1 = 0xE5, 0x3E, 0x3E
                        r2, g2, b2 = 0xFF, 0x50, 0x50
                        tt = (t - 0.5) / 0.5
                    rr = int(r1 + (r2 - r1) * tt)
                    gg = int(g1 + (g2 - g1) * tt)
                    bb = int(b1 + (b2 - b1) * tt)
                    color = f'#{rr:02x}{gg:02x}{bb:02x}'
                    bar_c.create_rectangle(i, 0, min(i + seg_w, fw), 4,
                                           fill=color, outline='', tags='bar')
                # Punta brillante (highlight a la derecha)
                tip_w = min(8, fw)
                if tip_w > 0:
                    bar_c.create_rectangle(fw - tip_w, 0, fw, 4,
                                           fill=C['accent_light'], outline='', tags='bar')
                    bar_c.create_rectangle(fw - 1, 0, fw, 4,
                                           fill='#FFFFFF', outline='', tags='bar')
        bar_c._draw = _draw_bar

        # ── Bottom row: timer + file count ────────────────────────────────────
        bot = tk.Frame(outer, bg=C['bg_primary'])
        bot.pack(fill=tk.X, pady=(10, 0))

        timer = tk.Label(bot, text="⏱️ Tiempo: 00:00:00",
                         font=('Consolas', 9),
                         bg=C['bg_primary'], fg=C['text_secondary'])
        timer.pack(side=tk.LEFT)

        resources = tk.Label(bot, text="",
                             font=('Segoe UI', 8),
                             bg=C['bg_primary'], fg=C['text_secondary'])
        resources.pack(side=tk.RIGHT)

        # compat: hidden ttk bar
        pb = ttk.Progressbar(outer, mode='determinate', maximum=100,
                             style='Argus.Horizontal.TProgressbar')

        # percent label (compat — unused visually, ring replaces it)
        pct_lbl = tk.Label(outer, text="0%", font=cls.FONTS['big_pct'],
                           bg=C['bg_primary'], fg=C['bg_primary'])

        return {
            'container':  outer,
            'status':     status,
            'progress':   pb,
            'detail':     detail,
            'timer':      timer,
            'resources':  resources,
            'percent':    pct_lbl,
            '_canvas':    bar_c,
            '_ring':      ring_c,
        }

    # ── completion panel ──────────────────────────────────────────────────────
    @classmethod
    def create_completion_panel(cls, parent):
        C = cls.COLORS

        # No se hace .pack() — la ventana solo muestra header + progress
        outer = tk.Frame(parent, bg=C['bg_primary'])

        card = tk.Frame(outer, bg=C['bg_card'],
                        highlightbackground=C['border_bright'],
                        highlightthickness=1)
        card.pack(fill=tk.BOTH, expand=True)

        center = tk.Frame(card, bg=C['bg_card'])
        center.place(relx=0.5, rely=0.5, anchor='center')

        icon_c = tk.Canvas(center, width=48, height=48,
                           bg=C['bg_card'], highlightthickness=0)
        icon_c.pack(pady=(0, 14))
        icon_c.create_oval(2, 2, 46, 46,
                           outline=C['text_muted'], width=1.5,
                           fill=C['bg_card'])
        icon_c.create_line(14, 24, 21, 33, 34, 14,
                           fill=C['text_muted'], width=2,
                           joinstyle='round', capstyle='round')

        main_lbl = tk.Label(center,
                            text="Esperando inicio",
                            font=('Segoe UI', 13, 'bold'),
                            bg=C['bg_card'], fg=C['text_secondary'])
        main_lbl.pack()

        sub_lbl = tk.Label(center, text="",
                           font=('Segoe UI', 8),
                           bg=C['bg_card'], fg=C['text_muted'])
        sub_lbl.pack(pady=(4, 0))

        return {
            'outer':       outer,
            'card':        card,
            'icon_canvas': icon_c,
            'main_label':  main_lbl,
            'sub_label':   sub_lbl,
        }

    # ── button ────────────────────────────────────────────────────────────────
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
        btn.bind('<Enter>', lambda e: btn.config(bg=hv))
        btn.bind('<Leave>', lambda e: btn.config(bg=bg))
        return frame

    # ── hidden results section ────────────────────────────────────────────────
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

    # ── public helpers ────────────────────────────────────────────────────────
    @classmethod
    def set_status_badge(cls, text, color=None):
        if cls._status_badge is None:
            return
        col = color or cls.COLORS['accent']
        try:
            cls._status_badge.config(text=f"●  {text}", fg=col)
            # Animación de pulso del punto rojo cuando está escaneando
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

            # Variantes de color para el pulso
            try:
                r, g, b = int(base_color[1:3], 16), int(base_color[3:5], 16), int(base_color[5:7], 16)
            except Exception:
                r, g, b = 0xE5, 0x3E, 0x3E
            dim = f'#{int(r*0.5):02x}{int(g*0.5):02x}{int(b*0.5):02x}'

            def _tick():
                if cls._status_badge is None:
                    return
                try:
                    cls._badge_pulse_state = (cls._badge_pulse_state + 1) % 2
                    color_now = base_color if cls._badge_pulse_state else dim
                    cls._status_badge.config(text=f"●  {txt_only}", fg=color_now)
                    cls._badge_pulse_after = cls._status_badge.after(700, _tick)
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

    @classmethod
    def update_counter(cls, key, value):
        pass

    @classmethod
    def update_canvas_bar(cls, canvas, pct_val):
        try:
            if hasattr(canvas, '_draw'):
                canvas._draw(pct_val)
        except Exception:
            pass
        # Also update ring if accessible
        try:
            ring = cls._ring_canvas
            if ring and hasattr(ring, '_draw'):
                ring._draw(pct_val)
        except Exception:
            pass

    @classmethod
    def set_completion_state(cls, completion_widgets, success=True, message=None, sub=None):
        C = cls.COLORS
        icon_c   = completion_widgets.get('icon_canvas')
        main_lbl = completion_widgets.get('main_label')
        sub_lbl  = completion_widgets.get('sub_label')

        if icon_c:
            icon_c.delete('all')
            color = C['green_glow'] if success else C['red']
            color_dim = C['green'] if success else C['accent_deep']
            bg    = C['bg_card']
            # Halo exterior tenue (efecto glow)
            icon_c.create_oval(0, 0, 48, 48, outline=color_dim, width=1, fill=bg)
            # Borde principal
            icon_c.create_oval(3, 3, 45, 45, outline=color, width=2, fill=bg)
            # Borde interior leve
            icon_c.create_oval(6, 6, 42, 42, outline=color_dim, width=1, fill='')
            if success:
                # Sombra del check
                icon_c.create_line(15, 25, 22, 34, 35, 15,
                                   fill=color_dim, width=3,
                                   joinstyle='round', capstyle='round')
                # Check principal
                icon_c.create_line(14, 24, 21, 33, 34, 14,
                                   fill=color, width=2,
                                   joinstyle='round', capstyle='round')
            else:
                icon_c.create_line(15, 15, 33, 33, fill=color, width=2, capstyle='round')
                icon_c.create_line(33, 15, 15, 33, fill=color, width=2, capstyle='round')

        if main_lbl:
            txt = message or ("Escaneo completado" if success else "Error en el escaneo")
            main_lbl.config(text=txt, fg=C['green_glow'] if success else C['red'])

        if sub_lbl:
            sub_lbl.config(text=sub or "", fg=C['text_secondary'])
