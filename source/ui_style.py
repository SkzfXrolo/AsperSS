import tkinter as tk
from tkinter import ttk, scrolledtext
import os
import sys
import threading
import time


class ModernUI:
    """
    Argus Projects — Scanner UI v3
    Rediseño completo: two-column layout, live counters, canvas progress bar.
    """

    COLORS = {
        'bg_primary':   '#07071A',
        'bg_secondary': '#0B0B22',
        'bg_card':      '#0E0E2A',
        'bg_hover':     '#13133A',

        'text_primary':   '#E2E8F7',
        'text_secondary': '#6B6E9A',
        'text_muted':     '#2E3060',

        'accent':         '#8B5CF6',
        'accent_hover':   '#7C3AED',
        'accent_dim':     'rgba(139,92,246,0.12)',
        'green':          '#10B981',
        'amber':          '#F59E0B',
        'red':            '#F43F5E',
        'blue':           '#38BDF8',

        'border':         '#14143A',
        'border_bright':  '#1E1E50',
        'separator':      '#0F0F30',
    }

    FONTS = {
        'title':     ('Segoe UI', 20, 'bold'),
        'subtitle':  ('Segoe UI', 9),
        'heading':   ('Segoe UI', 10, 'bold'),
        'body':      ('Segoe UI', 10),
        'body_bold': ('Segoe UI', 10, 'bold'),
        'small':     ('Segoe UI', 8),
        'mono':      ('Consolas', 10),
        'button':    ('Segoe UI', 11, 'bold'),
        'counter':   ('Segoe UI', 26, 'bold'),
        'label_sm':  ('Segoe UI', 7, 'bold'),
    }

    _style_applied = False

    # ── public counters (updated by scanner) ─────────────────────────────────
    _counter_labels = {}   # {'critical': tk.Label, ...}
    _status_badge = None
    _phase_label = None

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
            thickness=4,
        )

    @staticmethod
    def apply_window_style(root):
        root.title("Argus Projects — Security Scanner Pro")
        sw = root.winfo_screenwidth()
        if sw <= 1366:
            w, h = 1100, 680
            mw, mh = 900, 580
        elif sw <= 1920:
            w, h = 1360, 820
            mw, mh = 1100, 660
        else:
            w, h = 1540, 920
            mw, mh = 1360, 800
        root.geometry(f"{w}x{h}")
        root.minsize(mw, mh)
        root.configure(bg=ModernUI.COLORS['bg_primary'])
        try:
            ico_path = os.path.join(ModernUI._base_path(), 'assets', 'logo.ico')
            if os.path.exists(ico_path):
                root.iconbitmap(ico_path)
        except Exception:
            pass

    @staticmethod
    def _base_path():
        if getattr(sys, 'frozen', False):
            return sys._MEIPASS
        return os.path.dirname(os.path.abspath(__file__))

    # ─────────────────────────────────────────────────────────────────────────
    #  HEADER
    # ─────────────────────────────────────────────────────────────────────────
    @classmethod
    def create_header(cls, parent):
        C = cls.COLORS
        hdr = tk.Frame(parent, bg=C['bg_secondary'])
        hdr.pack(fill=tk.X)

        # Accent top line
        tk.Frame(hdr, bg=C['accent'], height=2).pack(fill=tk.X)

        inner = tk.Frame(hdr, bg=C['bg_secondary'])
        inner.pack(fill=tk.X, padx=22, pady=10)

        # ── Logo + brand ─────────────────────────────────────────────────────
        left = tk.Frame(inner, bg=C['bg_secondary'])
        left.pack(side=tk.LEFT, fill=tk.Y)

        logo_path = os.path.join(cls._base_path(), 'assets', 'logo.png')
        try:
            if os.path.exists(logo_path):
                from tkinter import PhotoImage
                raw = PhotoImage(file=logo_path)
                ow, oh = raw.width(), raw.height()
                sx = max(1, ow // 44)
                sy = max(1, oh // 44)
                img = raw.subsample(sx, sy)
                lbl = tk.Label(left, image=img, bg=C['bg_secondary'])
                lbl.image = img
                lbl.pack(side=tk.LEFT, padx=(0, 14))
            else:
                raise FileNotFoundError
        except Exception:
            c = tk.Canvas(left, width=40, height=40, bg=C['bg_secondary'],
                          highlightthickness=0)
            c.pack(side=tk.LEFT, padx=(0, 12))
            c.create_polygon(20, 2, 2, 10, 2, 22, 20, 38, 38, 22, 38, 10,
                             fill='', outline=C['accent'], width=2)
            c.create_line(12, 19, 18, 26, 28, 13,
                          fill=C['accent'], width=2, joinstyle='round', capstyle='round')

        brand = tk.Frame(left, bg=C['bg_secondary'])
        brand.pack(side=tk.LEFT)
        tk.Label(brand, text="ARGUS PROJECTS",
                 font=cls.FONTS['title'],
                 bg=C['bg_secondary'], fg=C['text_primary'],
                 anchor='w').pack(anchor='w')
        tk.Label(brand,
                 text="Security Scanner Pro  •  Advanced Anti-Bypass Detection",
                 font=cls.FONTS['subtitle'],
                 bg=C['bg_secondary'], fg=C['text_secondary'],
                 anchor='w').pack(anchor='w', pady=(2, 0))

        # ── Right: status badge ───────────────────────────────────────────────
        right = tk.Frame(inner, bg=C['bg_secondary'])
        right.pack(side=tk.RIGHT, fill=tk.Y)

        badge_frame = tk.Frame(right, bg=C['bg_card'],
                               highlightbackground=C['border_bright'], highlightthickness=1)
        badge_frame.pack(side=tk.RIGHT, pady=2)
        badge = tk.Label(badge_frame, text="●  LISTO",
                         font=('Segoe UI', 9, 'bold'),
                         bg=C['bg_card'], fg=C['green'],
                         padx=12, pady=6)
        badge.pack()
        cls._status_badge = badge

        tk.Frame(hdr, bg=C['separator'], height=1).pack(fill=tk.X)
        return hdr

    # ─────────────────────────────────────────────────────────────────────────
    #  STAT CARDS ROW  (live counters: Critical / Suspicious / Low / Clean)
    # ─────────────────────────────────────────────────────────────────────────
    @classmethod
    def create_stat_cards(cls, parent):
        C = cls.COLORS
        outer = tk.Frame(parent, bg=C['bg_primary'])
        outer.pack(fill=tk.X, padx=18, pady=(10, 0))

        specs = [
            ('critical',    'CRÍTICOS',       C['red'],   '#1A0812'),
            ('suspicious',  'SOSPECHOSOS',    C['amber'], '#1A1208'),
            ('low',         'POCO SUSP.',     '#818CF8',  '#0D0D1A'),
            ('clean',       'NORMALES',       C['green'], '#081A12'),
        ]

        cls._counter_labels = {}
        for key, label, color, bg in specs:
            card = tk.Frame(outer, bg=bg,
                            highlightbackground=color + '40',
                            highlightthickness=1)
            card.pack(side=tk.LEFT, fill=tk.BOTH, expand=True, padx=(0, 8))

            # Top accent line
            tk.Frame(card, bg=color, height=2).pack(fill=tk.X)

            inner = tk.Frame(card, bg=bg)
            inner.pack(fill=tk.BOTH, expand=True, padx=14, pady=10)

            tk.Label(inner, text=label,
                     font=cls.FONTS['label_sm'],
                     bg=bg, fg=color + 'BB',
                     anchor='w').pack(anchor='w')

            num = tk.Label(inner, text="0",
                           font=cls.FONTS['counter'],
                           bg=bg, fg=color,
                           anchor='w')
            num.pack(anchor='w', pady=(2, 0))

            cls._counter_labels[key] = num

        return outer

    # ─────────────────────────────────────────────────────────────────────────
    #  PROGRESS SECTION
    # ─────────────────────────────────────────────────────────────────────────
    @classmethod
    def create_progress_section(cls, parent):
        cls._apply_ttk_style()
        C = cls.COLORS

        outer = tk.Frame(parent, bg=C['bg_primary'])
        outer.pack(fill=tk.X, padx=18, pady=(10, 6))

        card = tk.Frame(outer, bg=C['bg_card'],
                        highlightbackground=C['border_bright'], highlightthickness=1)
        card.pack(fill=tk.BOTH, expand=True)

        content = tk.Frame(card, bg=C['bg_card'])
        content.pack(fill=tk.BOTH, expand=True, padx=18, pady=12)

        # Row: PROGRESO label  +  percent
        top_row = tk.Frame(content, bg=C['bg_card'])
        top_row.pack(fill=tk.X, pady=(0, 6))

        tk.Label(top_row, text="PROGRESO",
                 font=cls.FONTS['label_sm'],
                 bg=C['bg_card'], fg=C['text_secondary']).pack(side=tk.LEFT)

        pct = tk.Label(top_row, text="0%",
                       font=('Consolas', 11, 'bold'),
                       bg=C['bg_card'], fg=C['accent'])
        pct.pack(side=tk.RIGHT)

        # Status label
        status = tk.Label(content, text="Iniciando escaneo exhaustivo",
                          font=('Segoe UI', 10),
                          bg=C['bg_card'], fg=C['text_primary'], anchor='w')
        status.pack(fill=tk.X, pady=(0, 8))

        # Custom Canvas progress bar (looks better than ttk)
        bar_height = 8
        bar_bg = tk.Frame(content, bg=C['bg_secondary'], height=bar_height)
        bar_bg.pack(fill=tk.X, pady=(0, 6))
        bar_bg.pack_propagate(False)

        canvas = tk.Canvas(bar_bg, height=bar_height,
                           bg=C['bg_secondary'],
                           highlightthickness=0, bd=0)
        canvas.pack(fill=tk.BOTH, expand=True)
        canvas._fill = None
        canvas._width = 0

        def _draw_bar(pct_val):
            canvas.delete('bar')
            w = canvas.winfo_width()
            if w < 2:
                return
            fill_w = int(w * pct_val / 100)
            if fill_w > 0:
                # Main fill
                canvas.create_rectangle(0, 0, fill_w, bar_height,
                                        fill=C['accent'], outline='', tags='bar')
                # Shine strip
                canvas.create_rectangle(0, 0, fill_w, 2,
                                        fill='#A78BFA', outline='', tags='bar')

        canvas._draw = _draw_bar

        # Detail text
        detail = tk.Label(content, text="Preparando sistema...",
                          font=cls.FONTS['small'],
                          bg=C['bg_card'], fg=C['text_secondary'], anchor='w')
        detail.pack(fill=tk.X, pady=(0, 8))

        # Bottom row: timer + resources
        bot = tk.Frame(content, bg=C['bg_card'])
        bot.pack(fill=tk.X)

        timer = tk.Label(bot, text="⏱  00:00:00",
                         font=('Consolas', 9),
                         bg=C['bg_card'], fg=C['blue'])
        timer.pack(side=tk.LEFT)

        resources = tk.Label(bot, text="",
                             font=cls.FONTS['small'],
                             bg=C['bg_card'], fg=C['text_secondary'])
        resources.pack(side=tk.RIGHT)

        # Fake ttk bar hidden — we use canvas instead
        pb = ttk.Progressbar(content, mode='determinate', maximum=100,
                             style='Argus.Horizontal.TProgressbar')
        # hidden — but kept so existing code that sets pb['value'] still works
        pb._canvas_ref = canvas

        return {
            'container': card,
            'status':    status,
            'progress':  pb,
            'detail':    detail,
            'timer':     timer,
            'resources': resources,
            'percent':   pct,
            '_canvas':   canvas,
        }

    # ─────────────────────────────────────────────────────────────────────────
    #  SCAN BUTTON
    # ─────────────────────────────────────────────────────────────────────────
    @classmethod
    def create_button(cls, parent, text, command, style='primary', icon=''):
        C = cls.COLORS
        label = f"{icon}  {text}" if icon else text

        if style == 'primary':
            bg = C['accent'];       hv = C['accent_hover']
            fg = '#FFFFFF';         px, py, fs = 32, 13, 11
        elif style == 'secondary':
            bg = C['bg_card'];      hv = C['bg_hover']
            fg = C['text_primary']; px, py, fs = 20, 9, 9
        else:
            bg = C['bg_secondary']; hv = C['bg_card']
            fg = C['text_secondary'];px, py, fs = 16, 7, 9

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

    # ─────────────────────────────────────────────────────────────────────────
    #  RESULTS SECTION
    # ─────────────────────────────────────────────────────────────────────────
    @classmethod
    def create_results_section(cls, parent):
        C = cls.COLORS

        outer = tk.Frame(parent, bg=C['bg_primary'])
        outer.pack(fill=tk.BOTH, expand=True, padx=18, pady=(0, 18))

        card = tk.Frame(outer, bg=C['bg_card'],
                        highlightbackground=C['border_bright'], highlightthickness=1)
        card.pack(fill=tk.BOTH, expand=True)

        # Header row
        hdr = tk.Frame(card, bg=C['bg_secondary'])
        hdr.pack(fill=tk.X)
        tk.Label(hdr, text="RESULTADOS",
                 font=cls.FONTS['label_sm'],
                 bg=C['bg_secondary'], fg=C['text_secondary'],
                 padx=18, pady=8).pack(side=tk.LEFT)

        title = tk.Label(hdr, text="",
                         font=cls.FONTS['small'],
                         bg=C['bg_secondary'], fg=C['text_muted'],
                         padx=18)
        title.pack(side=tk.RIGHT)

        tk.Frame(card, bg=C['separator'], height=1).pack(fill=tk.X)

        content = tk.Frame(card, bg=C['bg_card'])
        content.pack(fill=tk.BOTH, expand=True, padx=2, pady=2)

        ta = scrolledtext.ScrolledText(
            content, wrap=tk.WORD,
            font=cls.FONTS['mono'],
            bg=C['bg_card'], fg=C['text_primary'],
            padx=16, pady=12,
            insertbackground=C['accent'],
            selectbackground=C['bg_hover'],
            selectforeground=C['text_primary'],
            relief=tk.FLAT, bd=0, highlightthickness=0,
        )
        ta.pack(fill=tk.BOTH, expand=True)

        ta.tag_config('success', foreground=C['green'],
                      font=(cls.FONTS['mono'][0], cls.FONTS['mono'][1], 'bold'))
        ta.tag_config('warning', foreground=C['amber'],
                      font=(cls.FONTS['mono'][0], cls.FONTS['mono'][1], 'bold'))
        ta.tag_config('danger',  foreground=C['red'],
                      font=(cls.FONTS['mono'][0], cls.FONTS['mono'][1], 'bold'))
        ta.tag_config('info',    foreground=C['blue'],
                      font=(cls.FONTS['mono'][0], cls.FONTS['mono'][1], 'bold'))
        ta.tag_config('header',  foreground=C['text_primary'],
                      font=(cls.FONTS['mono'][0], cls.FONTS['mono'][1], 'bold'))
        ta.tag_config('muted',   foreground=C['text_secondary'])
        ta.tag_config('accent',  foreground=C['accent'],
                      font=(cls.FONTS['mono'][0], cls.FONTS['mono'][1], 'bold'))

        return {'container': card, 'text': ta, 'title': title}

    # ─────────────────────────────────────────────────────────────────────────
    #  PUBLIC HELPERS (called by scanner during scan)
    # ─────────────────────────────────────────────────────────────────────────
    @classmethod
    def set_status_badge(cls, text, color=None):
        """Update the header status badge (e.g. SCANNING, DONE)."""
        if cls._status_badge is None:
            return
        C = cls.COLORS
        col = color or C['accent']
        try:
            cls._status_badge.config(text=f"●  {text}", fg=col)
        except Exception:
            pass

    @classmethod
    def update_counter(cls, key, value):
        """Update a live stat counter. key: 'critical'|'suspicious'|'low'|'clean'"""
        lbl = cls._counter_labels.get(key)
        if lbl is None:
            return
        try:
            lbl.config(text=str(value))
        except Exception:
            pass

    @classmethod
    def update_canvas_bar(cls, canvas, pct_val):
        """Redraw the custom canvas progress bar."""
        try:
            if hasattr(canvas, '_draw'):
                canvas._draw(pct_val)
        except Exception:
            pass
