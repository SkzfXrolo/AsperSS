import tkinter as tk
from tkinter import ttk, scrolledtext
import os
import sys


class ModernUI:
    """
    Argus Projects — Scanner UI v4
    El jugador solo ve: header + progreso + estado final.
    Los resultados se envían al panel web del staff — nunca se muestran aquí.
    """

    COLORS = {
        'bg_primary':   '#07071A',
        'bg_secondary': '#0B0B22',
        'bg_card':      '#0E0E2A',
        'bg_hover':     '#13133A',

        'text_primary':   '#E2E8F7',
        'text_secondary': '#6B6E9A',
        'text_muted':     '#2E3060',

        'accent':       '#8B5CF6',
        'accent_hover': '#7C3AED',
        'green':        '#10B981',
        'amber':        '#F59E0B',
        'red':          '#F43F5E',
        'blue':         '#38BDF8',

        'border':       '#14143A',
        'border_bright':'#1E1E50',
        'separator':    '#0F0F30',
    }

    FONTS = {
        'title':    ('Segoe UI', 20, 'bold'),
        'subtitle': ('Segoe UI', 9),
        'body':     ('Segoe UI', 10),
        'small':    ('Segoe UI', 8),
        'mono':     ('Consolas', 10),
        'label_sm': ('Segoe UI', 7, 'bold'),
        'phase':    ('Segoe UI', 12),
        'done':     ('Segoe UI', 14, 'bold'),
    }

    _style_applied = False
    _status_badge  = None

    # ── ttk style ────────────────────────────────────────────────────────────
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

    # ── window ───────────────────────────────────────────────────────────────
    @staticmethod
    def apply_window_style(root):
        root.title("Argus Projects — Security Scanner Pro")
        sw = root.winfo_screenwidth()
        if sw <= 1366:
            w, h = 740, 480
        elif sw <= 1920:
            w, h = 880, 540
        else:
            w, h = 980, 600
        root.geometry(f"{w}x{h}")
        root.minsize(660, 420)
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

    # ── header ───────────────────────────────────────────────────────────────
    @classmethod
    def create_header(cls, parent):
        C = cls.COLORS
        hdr = tk.Frame(parent, bg=C['bg_secondary'])
        hdr.pack(fill=tk.X)

        tk.Frame(hdr, bg=C['accent'], height=2).pack(fill=tk.X)

        inner = tk.Frame(hdr, bg=C['bg_secondary'])
        inner.pack(fill=tk.X, padx=24, pady=12)

        left = tk.Frame(inner, bg=C['bg_secondary'])
        left.pack(side=tk.LEFT, fill=tk.Y)

        # Logo
        logo_path = os.path.join(cls._base_path(), 'assets', 'logo.png')
        try:
            if os.path.exists(logo_path):
                from tkinter import PhotoImage
                raw = PhotoImage(file=logo_path)
                sx = max(1, raw.width()  // 44)
                sy = max(1, raw.height() // 44)
                img = raw.subsample(sx, sy)
                lbl = tk.Label(left, image=img, bg=C['bg_secondary'])
                lbl.image = img
                lbl.pack(side=tk.LEFT, padx=(0, 14))
            else:
                raise FileNotFoundError
        except Exception:
            c = tk.Canvas(left, width=40, height=40,
                          bg=C['bg_secondary'], highlightthickness=0)
            c.pack(side=tk.LEFT, padx=(0, 12))
            c.create_polygon(20,2, 2,10, 2,22, 20,38, 38,22, 38,10,
                             fill='', outline=C['accent'], width=2)
            c.create_line(12,19, 18,26, 28,13,
                          fill=C['accent'], width=2,
                          joinstyle='round', capstyle='round')

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

        # Badge
        badge_wrap = tk.Frame(inner, bg=C['bg_card'],
                              highlightbackground=C['border_bright'],
                              highlightthickness=1)
        badge_wrap.pack(side=tk.RIGHT, pady=2)
        badge = tk.Label(badge_wrap, text="●  LISTO",
                         font=('Segoe UI', 9, 'bold'),
                         bg=C['bg_card'], fg=C['green'],
                         padx=14, pady=7)
        badge.pack()
        cls._status_badge = badge

        tk.Frame(hdr, bg=C['separator'], height=1).pack(fill=tk.X)
        return hdr

    # ── progress section ─────────────────────────────────────────────────────
    @classmethod
    def create_progress_section(cls, parent):
        cls._apply_ttk_style()
        C = cls.COLORS

        outer = tk.Frame(parent, bg=C['bg_primary'])
        outer.pack(fill=tk.X, padx=24, pady=(18, 10))

        card = tk.Frame(outer, bg=C['bg_card'],
                        highlightbackground=C['border_bright'],
                        highlightthickness=1)
        card.pack(fill=tk.BOTH, expand=True)

        content = tk.Frame(card, bg=C['bg_card'])
        content.pack(fill=tk.BOTH, expand=True, padx=22, pady=16)

        # Row: label + percent
        top = tk.Frame(content, bg=C['bg_card'])
        top.pack(fill=tk.X, pady=(0, 8))
        tk.Label(top, text="PROGRESO",
                 font=cls.FONTS['label_sm'],
                 bg=C['bg_card'], fg=C['text_secondary']).pack(side=tk.LEFT)
        pct = tk.Label(top, text="0%",
                       font=('Consolas', 11, 'bold'),
                       bg=C['bg_card'], fg=C['accent'])
        pct.pack(side=tk.RIGHT)

        # Phase text (what the scanner is doing right now)
        status = tk.Label(content, text="Esperando inicio...",
                          font=cls.FONTS['phase'],
                          bg=C['bg_card'], fg=C['text_primary'], anchor='w')
        status.pack(fill=tk.X, pady=(0, 10))

        # Canvas bar
        bar_bg = tk.Frame(content, bg=C['bg_secondary'], height=10)
        bar_bg.pack(fill=tk.X, pady=(0, 8))
        bar_bg.pack_propagate(False)

        canvas = tk.Canvas(bar_bg, height=10,
                           bg=C['bg_secondary'],
                           highlightthickness=0, bd=0)
        canvas.pack(fill=tk.BOTH, expand=True)

        def _draw(pct_val):
            canvas.delete('bar')
            w = canvas.winfo_width()
            if w < 2:
                return
            fw = max(0, int(w * pct_val / 100))
            if fw > 0:
                canvas.create_rectangle(0, 0, fw, 10,
                                        fill=C['accent'], outline='', tags='bar')
                canvas.create_rectangle(0, 0, fw, 3,
                                        fill='#A78BFA', outline='', tags='bar')
        canvas._draw = _draw

        # Detail / sub-status
        detail = tk.Label(content, text="",
                          font=cls.FONTS['small'],
                          bg=C['bg_card'], fg=C['text_secondary'], anchor='w')
        detail.pack(fill=tk.X, pady=(0, 10))

        # Timer + resources
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

        # Hidden ttk bar (compatibility — existing code sets pb['value'])
        pb = ttk.Progressbar(content, mode='determinate', maximum=100,
                             style='Argus.Horizontal.TProgressbar')

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

    # ── completion panel ─────────────────────────────────────────────────────
    @classmethod
    def create_completion_panel(cls, parent):
        """Shown after scan finishes — replaces 'results' area for the user."""
        C = cls.COLORS

        outer = tk.Frame(parent, bg=C['bg_primary'])
        outer.pack(fill=tk.BOTH, expand=True, padx=24, pady=(0, 24))

        card = tk.Frame(outer, bg=C['bg_card'],
                        highlightbackground=C['border_bright'],
                        highlightthickness=1)
        card.pack(fill=tk.BOTH, expand=True)

        # Vertical center
        center = tk.Frame(card, bg=C['bg_card'])
        center.place(relx=0.5, rely=0.5, anchor='center')

        # Icon area (canvas circle)
        icon_c = tk.Canvas(center, width=64, height=64,
                           bg=C['bg_card'], highlightthickness=0)
        icon_c.pack(pady=(0, 16))
        icon_c.create_oval(4, 4, 60, 60,
                           outline=C['green'], width=2, fill='#081A12')
        icon_c.create_line(18, 32, 28, 44, 46, 20,
                           fill=C['green'], width=3,
                           joinstyle='round', capstyle='round')

        waiting_text = tk.Label(center,
                                text="Esperando inicio del escaneo",
                                font=cls.FONTS['done'],
                                bg=C['bg_card'], fg=C['text_secondary'])
        waiting_text.pack()

        sub = tk.Label(center,
                       text="Presiona el botón para comenzar",
                       font=cls.FONTS['small'],
                       bg=C['bg_card'], fg=C['text_muted'])
        sub.pack(pady=(6, 0))

        return {
            'outer':        outer,
            'card':         card,
            'icon_canvas':  icon_c,
            'main_label':   waiting_text,
            'sub_label':    sub,
        }

    # ── button ────────────────────────────────────────────────────────────────
    @classmethod
    def create_button(cls, parent, text, command, style='primary', icon=''):
        C = cls.COLORS
        label = f"{icon}  {text}" if icon else text

        if style == 'primary':
            bg = C['accent'];        hv = C['accent_hover']
            fg = '#FFFFFF';          px, py, fs = 32, 14, 12
        elif style == 'secondary':
            bg = C['bg_card'];       hv = C['bg_hover']
            fg = C['text_primary'];  px, py, fs = 20, 10, 9
        else:
            bg = C['bg_secondary'];  hv = C['bg_card']
            fg = C['text_secondary'];px, py, fs = 16, 8, 9

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

    # ── hidden results section (staff data never shown to user) ───────────────
    @classmethod
    def create_results_section(cls, parent):
        """
        Creates the ScrolledText that existing code writes to,
        but hides it completely from the user.
        """
        C = cls.COLORS

        # Hidden frame with zero height — invisible but existing
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

        # Keep all existing tags so code doesn't error
        for tag, color in [('success', C['green']), ('warning', C['amber']),
                            ('danger', C['red']),   ('info',    C['blue']),
                            ('header', C['text_primary']), ('muted', C['text_secondary']),
                            ('accent', C['accent'])]:
            ta.tag_config(tag, foreground=color)

        # title label also expected by main.py
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
        pass  # counters hidden in v4 — staff sees them on web panel

    @classmethod
    def update_canvas_bar(cls, canvas, pct_val):
        try:
            if hasattr(canvas, '_draw'):
                canvas._draw(pct_val)
        except Exception:
            pass

    @classmethod
    def set_completion_state(cls, completion_widgets, success=True, message=None, sub=None):
        """Update the completion panel after scan finishes."""
        C = cls.COLORS
        icon_c  = completion_widgets.get('icon_canvas')
        main_lbl = completion_widgets.get('main_label')
        sub_lbl  = completion_widgets.get('sub_label')

        if icon_c:
            icon_c.delete('all')
            color = C['green'] if success else C['red']
            bg    = '#081A12'  if success else '#1A0812'
            icon_c.create_oval(4, 4, 60, 60,
                               outline=color, width=2, fill=bg)
            if success:
                icon_c.create_line(18, 32, 28, 44, 46, 20,
                                   fill=color, width=3,
                                   joinstyle='round', capstyle='round')
            else:
                icon_c.create_line(20, 20, 44, 44,
                                   fill=color, width=3, capstyle='round')
                icon_c.create_line(44, 20, 20, 44,
                                   fill=color, width=3, capstyle='round')

        if main_lbl:
            txt   = message or ("Escaneo completado" if success else "Error en el escaneo")
            color = C['green']  if success else C['red']
            main_lbl.config(text=txt, fg=color)

        if sub_lbl:
            stxt  = sub or ("Los resultados han sido enviados al staff" if success else "Contacta al administrador")
            sub_lbl.config(text=stxt, fg=C['text_secondary'])
