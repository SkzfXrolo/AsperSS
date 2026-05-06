import tkinter as tk
from tkinter import ttk, scrolledtext
import os
import sys


class ModernUI:
    """Argus Projects — Scanner UI v5. Compacto, progreso suave 1-100."""

    COLORS = {
        'bg_primary':   '#09091C',
        'bg_secondary': '#0C0C22',
        'bg_card':      '#0F0F28',
        'bg_hover':     '#13133A',

        'text_primary':   '#E4E8F5',
        'text_secondary': '#545880',
        'text_muted':     '#252548',

        'accent':       '#7C3AED',
        'accent_light': '#A78BFA',
        'accent_hover': '#6D28D9',
        'green':        '#10B981',
        'amber':        '#F59E0B',
        'red':          '#EF4444',
        'blue':         '#38BDF8',

        'border':       '#181838',
        'border_bright':'#242460',
        'separator':    '#0E0E26',
    }

    FONTS = {
        'title':    ('Segoe UI', 13, 'bold'),
        'subtitle': ('Segoe UI', 8),
        'body':     ('Segoe UI', 10),
        'small':    ('Segoe UI', 8),
        'mono':     ('Consolas', 9),
        'label_sm': ('Segoe UI', 7, 'bold'),
        'phase':    ('Segoe UI', 10),
        'done':     ('Segoe UI', 13, 'bold'),
        'big_pct':  ('Segoe UI', 36, 'bold'),
    }

    _style_applied = False
    _status_badge  = None

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

    # ── window ────────────────────────────────────────────────────────────────
    @staticmethod
    def apply_window_style(root):
        root.title("Argus Scanner — ASPERS Projects")
        sw = root.winfo_screenwidth()
        if sw <= 1366:
            w, h = 660, 420
        elif sw <= 1920:
            w, h = 760, 460
        else:
            w, h = 860, 520
        root.geometry(f"{w}x{h}")
        root.minsize(600, 380)
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

        hdr = tk.Frame(parent, bg=C['bg_secondary'])
        hdr.pack(fill=tk.X)

        # Línea de acento superior (2px)
        tk.Frame(hdr, bg=C['accent'], height=2).pack(fill=tk.X)

        inner = tk.Frame(hdr, bg=C['bg_secondary'])
        inner.pack(fill=tk.X, padx=20, pady=10)

        # Izquierda: logo + nombre
        left = tk.Frame(inner, bg=C['bg_secondary'])
        left.pack(side=tk.LEFT, fill=tk.Y)

        # Logo
        logo_path = os.path.join(cls._base_path(), 'assets', 'logo.png')
        try:
            if os.path.exists(logo_path):
                from tkinter import PhotoImage
                raw = PhotoImage(file=logo_path)
                sx = max(1, raw.width()  // 32)
                sy = max(1, raw.height() // 32)
                img = raw.subsample(sx, sy)
                lbl = tk.Label(left, image=img, bg=C['bg_secondary'])
                lbl.image = img
                lbl.pack(side=tk.LEFT, padx=(0, 10))
            else:
                raise FileNotFoundError
        except Exception:
            c = tk.Canvas(left, width=32, height=32,
                          bg=C['bg_secondary'], highlightthickness=0)
            c.pack(side=tk.LEFT, padx=(0, 10))
            c.create_polygon(16,2, 2,8, 2,18, 16,30, 30,18, 30,8,
                             fill='', outline=C['accent'], width=2)
            c.create_line(10,15, 14,21, 22,10,
                          fill=C['accent'], width=2,
                          joinstyle='round', capstyle='round')

        brand = tk.Frame(left, bg=C['bg_secondary'])
        brand.pack(side=tk.LEFT)
        tk.Label(brand, text="ARGUS PROJECTS",
                 font=cls.FONTS['title'],
                 bg=C['bg_secondary'], fg=C['text_primary'],
                 anchor='w').pack(anchor='w')
        tk.Label(brand,
                 text="Security Scanner  •  Anti-Bypass Detection",
                 font=cls.FONTS['subtitle'],
                 bg=C['bg_secondary'], fg=C['text_secondary'],
                 anchor='w').pack(anchor='w', pady=(1, 0))

        # Derecha: badge de estado
        badge_wrap = tk.Frame(inner, bg=C['bg_card'],
                              highlightbackground=C['border_bright'],
                              highlightthickness=1)
        badge_wrap.pack(side=tk.RIGHT, pady=2)
        badge = tk.Label(badge_wrap, text="●  LISTO",
                         font=('Segoe UI', 8, 'bold'),
                         bg=C['bg_card'], fg=C['green'],
                         padx=12, pady=6)
        badge.pack()
        cls._status_badge = badge

        tk.Frame(hdr, bg=C['separator'], height=1).pack(fill=tk.X)
        return hdr

    # ── progress section ──────────────────────────────────────────────────────
    @classmethod
    def create_progress_section(cls, parent):
        cls._apply_ttk_style()
        C = cls.COLORS

        outer = tk.Frame(parent, bg=C['bg_primary'])
        outer.pack(fill=tk.X, padx=20, pady=(16, 8))

        card = tk.Frame(outer, bg=C['bg_card'],
                        highlightbackground=C['border_bright'],
                        highlightthickness=1)
        card.pack(fill=tk.BOTH, expand=True)

        content = tk.Frame(card, bg=C['bg_card'])
        content.pack(fill=tk.BOTH, expand=True, padx=20, pady=14)

        # Fila superior: porcentaje grande (izq) + label PROGRESO (der)
        top = tk.Frame(content, bg=C['bg_card'])
        top.pack(fill=tk.X, pady=(0, 4))

        pct = tk.Label(top, text="0%",
                       font=cls.FONTS['big_pct'],
                       bg=C['bg_card'], fg=C['accent'])
        pct.pack(side=tk.LEFT, anchor='w')

        tk.Label(top, text="ANÁLISIS EN CURSO",
                 font=cls.FONTS['label_sm'],
                 bg=C['bg_card'], fg=C['text_secondary']).pack(side=tk.RIGHT, anchor='e')

        # Barra de progreso canvas (6px, redondeada con rectángulos)
        bar_bg = tk.Frame(content, bg=C['border'], height=6)
        bar_bg.pack(fill=tk.X, pady=(0, 8))
        bar_bg.pack_propagate(False)

        canvas = tk.Canvas(bar_bg, height=6,
                           bg=C['border'],
                           highlightthickness=0, bd=0)
        canvas.pack(fill=tk.BOTH, expand=True)

        def _draw(pct_val):
            canvas.delete('bar')
            w = canvas.winfo_width()
            if w < 2:
                return
            fw = max(0, int(w * pct_val / 100))
            if fw > 0:
                # Cuerpo principal
                canvas.create_rectangle(0, 0, fw, 6,
                                        fill=C['accent'], outline='', tags='bar')
                # Brillo superior (línea de 2px más clara)
                canvas.create_rectangle(0, 0, fw, 2,
                                        fill=C['accent_light'], outline='', tags='bar')
        canvas._draw = _draw

        # Fase actual (módulo en curso)
        status = tk.Label(content, text="Esperando inicio...",
                          font=cls.FONTS['phase'],
                          bg=C['bg_card'], fg=C['text_primary'], anchor='w')
        status.pack(fill=tk.X, pady=(0, 4))

        # Detalle / submensaje
        detail = tk.Label(content, text="",
                          font=cls.FONTS['small'],
                          bg=C['bg_card'], fg=C['text_secondary'], anchor='w')
        detail.pack(fill=tk.X, pady=(0, 8))

        # Timer + recursos
        bot = tk.Frame(content, bg=C['bg_card'])
        bot.pack(fill=tk.X)
        timer = tk.Label(bot, text="⏱  00:00:00",
                         font=cls.FONTS['mono'],
                         bg=C['bg_card'], fg=C['blue'])
        timer.pack(side=tk.LEFT)
        resources = tk.Label(bot, text="",
                             font=cls.FONTS['small'],
                             bg=C['bg_card'], fg=C['text_secondary'])
        resources.pack(side=tk.RIGHT)

        # Hidden ttk bar (compat)
        pb = ttk.Progressbar(content, mode='determinate', maximum=100,
                             style='Argus.Horizontal.TProgressbar')

        return {
            'container':  card,
            'status':     status,
            'progress':   pb,
            'detail':     detail,
            'timer':      timer,
            'resources':  resources,
            'percent':    pct,
            '_canvas':    canvas,
        }

    # ── completion panel ──────────────────────────────────────────────────────
    @classmethod
    def create_completion_panel(cls, parent):
        C = cls.COLORS

        outer = tk.Frame(parent, bg=C['bg_primary'])
        outer.pack(fill=tk.BOTH, expand=True, padx=20, pady=(0, 20))

        card = tk.Frame(outer, bg=C['bg_card'],
                        highlightbackground=C['border_bright'],
                        highlightthickness=1)
        card.pack(fill=tk.BOTH, expand=True)

        center = tk.Frame(card, bg=C['bg_card'])
        center.place(relx=0.5, rely=0.5, anchor='center')

        # Ícono (canvas, circulo con check/x)
        icon_c = tk.Canvas(center, width=52, height=52,
                           bg=C['bg_card'], highlightthickness=0)
        icon_c.pack(pady=(0, 12))
        icon_c.create_oval(3, 3, 49, 49,
                           outline=C['green'], width=2, fill='#071612')
        icon_c.create_line(15, 26, 23, 36, 38, 16,
                           fill=C['green'], width=2.5,
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
        sub.pack(pady=(5, 0))

        return {
            'outer':       outer,
            'card':        card,
            'icon_canvas': icon_c,
            'main_label':  waiting_text,
            'sub_label':   sub,
        }

    # ── button ────────────────────────────────────────────────────────────────
    @classmethod
    def create_button(cls, parent, text, command, style='primary', icon=''):
        C = cls.COLORS
        label = f"{icon}  {text}" if icon else text

        if style == 'primary':
            bg = C['accent'];        hv = C['accent_hover']
            fg = '#FFFFFF';          px, py, fs = 28, 12, 11
        elif style == 'secondary':
            bg = C['bg_card'];       hv = C['bg_hover']
            fg = C['text_primary'];  px, py, fs = 18, 9, 9
        else:
            bg = C['bg_secondary'];  hv = C['bg_card']
            fg = C['text_secondary'];px, py, fs = 14, 7, 8

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

    # ── helpers públicos ──────────────────────────────────────────────────────
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

    @classmethod
    def set_completion_state(cls, completion_widgets, success=True, message=None, sub=None):
        C = cls.COLORS
        icon_c   = completion_widgets.get('icon_canvas')
        main_lbl = completion_widgets.get('main_label')
        sub_lbl  = completion_widgets.get('sub_label')

        if icon_c:
            icon_c.delete('all')
            color = C['green'] if success else C['red']
            bg    = '#071612'  if success else '#180810'
            icon_c.create_oval(3, 3, 49, 49, outline=color, width=2, fill=bg)
            if success:
                icon_c.create_line(15, 26, 23, 36, 38, 16,
                                   fill=color, width=2.5,
                                   joinstyle='round', capstyle='round')
            else:
                icon_c.create_line(16, 16, 36, 36,
                                   fill=color, width=2.5, capstyle='round')
                icon_c.create_line(36, 16, 16, 36,
                                   fill=color, width=2.5, capstyle='round')

        if main_lbl:
            txt   = message or ("Escaneo completado" if success else "Error en el escaneo")
            main_lbl.config(text=txt, fg=C['green'] if success else C['red'])

        if sub_lbl:
            stxt = sub or ("Los resultados han sido enviados al staff" if success else "Contacta al administrador")
            sub_lbl.config(text=stxt, fg=C['text_secondary'])
