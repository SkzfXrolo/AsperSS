import tkinter as tk
from tkinter import ttk, scrolledtext
import os
import sys
import math


class ModernUI:
    """Argus Scanner — Echo-inspired UI. Dark, red accent, minimal."""

    COLORS = {
        'bg_primary':   '#0D0D0D',
        'bg_secondary': '#111111',
        'bg_card':      '#161616',
        'bg_hover':     '#1C1C1C',

        'text_primary':   '#F0F0F0',
        'text_secondary': '#666666',
        'text_muted':     '#333333',

        'accent':       '#E53E3E',
        'accent_light': '#FC8181',
        'accent_hover': '#C53030',
        'green':        '#48BB78',
        'amber':        '#ECC94B',
        'red':          '#FC5555',
        'blue':         '#63B3ED',

        'border':       '#1E1E1E',
        'border_bright':'#2A2A2A',
        'separator':    '#181818',
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
        sw = root.winfo_screenwidth()
        if sw <= 1366:
            w, h = 620, 400
        elif sw <= 1920:
            w, h = 700, 440
        else:
            w, h = 760, 480
        x = (root.winfo_screenwidth()  - w) // 2
        y = (root.winfo_screenheight() - h) // 2
        root.geometry(f"{w}x{h}+{x}+{y}")
        root.minsize(580, 360)
        root.resizable(False, False)
        root.configure(bg=ModernUI.COLORS['bg_primary'])
        try:
            ico = os.path.join(ModernUI._base_path(), 'assets', 'logo.ico')
            if os.path.exists(ico):
                root.iconbitmap(ico)
        except Exception:
            pass

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
        inner.pack(fill=tk.X, padx=24, pady=(14, 12))

        # Left: brand
        left = tk.Frame(inner, bg=C['bg_primary'])
        left.pack(side=tk.LEFT, fill=tk.Y)

        # Shield icon via canvas
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
        outer.pack(fill=tk.BOTH, expand=True, padx=24, pady=(20, 8))

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

        def _draw_ring(pct):
            ring_c.delete('all')
            pad = 10
            x0, y0 = pad, pad
            x1, y1 = ring_size - pad, ring_size - pad

            # Track (full grey circle)
            ring_c.create_arc(x0, y0, x1, y1,
                              start=90, extent=360,
                              style='arc', outline=C['border_bright'], width=6)

            # Progress arc
            if pct > 0:
                extent = -int(360 * pct / 100)
                ring_c.create_arc(x0, y0, x1, y1,
                                  start=90, extent=extent,
                                  style='arc', outline=C['accent'], width=6)

            # Center percentage text
            ring_c.create_text(ring_size // 2, ring_size // 2,
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
        bar_wrap = tk.Frame(outer, bg=C['border'], height=3)
        bar_wrap.pack(fill=tk.X, pady=(18, 0))
        bar_wrap.pack_propagate(False)
        bar_c = tk.Canvas(bar_wrap, height=3,
                          bg=C['border'], highlightthickness=0, bd=0)
        bar_c.pack(fill=tk.BOTH, expand=True)

        def _draw_bar(pct_val):
            bar_c.delete('bar')
            w = bar_c.winfo_width()
            if w < 2:
                return
            fw = max(0, int(w * pct_val / 100))
            if fw > 0:
                bar_c.create_rectangle(0, 0, fw, 3,
                                       fill=C['accent'], outline='', tags='bar')
        bar_c._draw = _draw_bar

        # ── Bottom row: timer + file count ────────────────────────────────────
        bot = tk.Frame(outer, bg=C['bg_primary'])
        bot.pack(fill=tk.X, pady=(10, 0))

        timer = tk.Label(bot, text="00:00:00",
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

        outer = tk.Frame(parent, bg=C['bg_primary'])
        outer.pack(fill=tk.BOTH, expand=True, padx=24, pady=(0, 20))

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
        except Exception:
            pass

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
            color = C['green'] if success else C['red']
            bg    = C['bg_card']
            icon_c.create_oval(2, 2, 46, 46, outline=color, width=1.5, fill=bg)
            if success:
                icon_c.create_line(14, 24, 21, 33, 34, 14,
                                   fill=color, width=2,
                                   joinstyle='round', capstyle='round')
            else:
                icon_c.create_line(15, 15, 33, 33, fill=color, width=2, capstyle='round')
                icon_c.create_line(33, 15, 15, 33, fill=color, width=2, capstyle='round')

        if main_lbl:
            txt = message or ("Escaneo completado" if success else "Error en el escaneo")
            main_lbl.config(text=txt, fg=C['green'] if success else C['red'])

        if sub_lbl:
            sub_lbl.config(text=sub or "", fg=C['text_secondary'])
