import tkinter as tk
from tkinter import ttk, scrolledtext

class ModernUI:
    """
    ASPERS Projects — Scanner UI
    Paleta oscura premium (midnight navy + cyan) alineada con el panel web.
    """

    COLORS = {
        # Fondos — Aurora: espacio profundo índigo
        'bg_primary':   '#09091C',
        'bg_secondary': '#0E0E28',
        'bg_tertiary':  '#141430',
        'card':         '#0C0C26',

        # Textos
        'text_primary':   '#E2E8F7',
        'text_secondary': '#7C7FA6',
        'text_muted':     '#3D3F6E',

        # Acentos — Aurora: violeta eléctrico
        'accent_primary':       '#8B5CF6',
        'accent_primary_hover': '#6D28D9',
        'accent_secondary':     '#10B981',
        'accent_warning':       '#F59E0B',
        'accent_danger':        '#F43F5E',
        'accent_info':          '#38BDF8',

        # Bordes
        'border':       '#1A1A38',
        'border_light': '#141430',
    }

    FONTS = {
        'title':     ('Segoe UI', 22, 'bold'),
        'subtitle':  ('Segoe UI', 9),
        'heading':   ('Segoe UI', 11, 'bold'),
        'body':      ('Segoe UI', 10),
        'body_bold': ('Segoe UI', 10, 'bold'),
        'small':     ('Segoe UI', 9),
        'mono':      ('Consolas', 10),
        'button':    ('Segoe UI', 10, 'bold'),
    }

    # ── Estilos ttk ──────────────────────────────────────────────────────────
    _style_applied = False

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
            'Aspers.Horizontal.TProgressbar',
            background=cls.COLORS['accent_primary'],
            troughcolor='#0d1a2e',
            borderwidth=0,
            lightcolor=cls.COLORS['accent_primary'],
            darkcolor=cls.COLORS['accent_primary'],
            thickness=6,
        )

    # ── Aplicar ventana ──────────────────────────────────────────────────────
    @staticmethod
    def apply_window_style(root):
        root.title("ASPERS Projects — Security Scanner Pro")
        sw = root.winfo_screenwidth()
        if sw <= 1366:
            w, h = 1150, 670
            mw, mh = 960, 560
        elif sw <= 1920:
            w, h = 1380, 820
            mw, mh = 1150, 660
        else:
            w, h = 1560, 920
            mw, mh = 1380, 800
        root.geometry(f"{w}x{h}")
        root.minsize(mw, mh)
        root.configure(bg=ModernUI.COLORS['bg_primary'])
        try:
            root.attributes('-alpha', 1.0)
        except Exception:
            pass

    # ── Header ───────────────────────────────────────────────────────────────
    @staticmethod
    def create_header(parent):
        C = ModernUI.COLORS
        hdr = tk.Frame(parent, bg=C['bg_secondary'])
        hdr.pack(fill=tk.X)

        # Línea cyan superior (accent bar)
        tk.Frame(hdr, bg=C['accent_primary'], height=2).pack(fill=tk.X)

        inner = tk.Frame(hdr, bg=C['bg_secondary'])
        inner.pack(fill=tk.X, padx=24, pady=14)

        left = tk.Frame(inner, bg=C['bg_secondary'])
        left.pack(side=tk.LEFT, fill=tk.Y)

        # Logo (canvas shield)
        logo_c = tk.Canvas(left, width=38, height=38, bg=C['bg_secondary'],
                           highlightthickness=0)
        logo_c.pack(side=tk.LEFT, padx=(0, 12))
        logo_c.create_polygon(19, 2, 3, 9, 3, 20, 19, 36, 35, 20, 35, 9,
                              fill='', outline=C['accent_primary'], width=2)
        logo_c.create_oval(11, 10, 27, 26,
                           fill='', outline=C['accent_secondary'], width=1)
        logo_c.create_line(12, 18, 17, 24, 26, 13,
                           fill=C['accent_primary'], width=2,
                           joinstyle='round', capstyle='round')

        text_col = tk.Frame(left, bg=C['bg_secondary'])
        text_col.pack(side=tk.LEFT)
        tk.Label(text_col, text="ASPERS PROJECTS",
                 font=ModernUI.FONTS['title'],
                 bg=C['bg_secondary'], fg=C['text_primary'],
                 anchor='w').pack(anchor='w')
        tk.Label(text_col,
                 text="Security Scanner Pro  •  Advanced Anti-Bypass Detection",
                 font=ModernUI.FONTS['subtitle'],
                 bg=C['bg_secondary'], fg=C['text_secondary'],
                 anchor='w').pack(anchor='w', pady=(2, 0))

        # Badge derecho
        badge = tk.Label(inner, text="● READY",
                         font=('Segoe UI', 9, 'bold'),
                         bg=C['bg_secondary'], fg=C['accent_secondary'],
                         padx=0)
        badge.pack(side=tk.RIGHT, padx=4)

        # Línea inferior
        tk.Frame(hdr, bg='#0d1a2e', height=1).pack(fill=tk.X)
        return hdr

    # ── Sección de progreso ──────────────────────────────────────────────────
    @staticmethod
    def create_progress_section(parent):
        ModernUI._apply_ttk_style()
        C = ModernUI.COLORS

        outer = tk.Frame(parent, bg=C['bg_primary'])
        outer.pack(fill=tk.X, padx=18, pady=(12, 6))

        card = tk.Frame(outer, bg=C['card'])
        card.pack(fill=tk.BOTH, expand=True)
        tk.Frame(card, bg=C['accent_primary'], height=1).pack(fill=tk.X)

        content = tk.Frame(card, bg=C['card'])
        content.pack(fill=tk.BOTH, expand=True, padx=18, pady=12)

        # Fila: título + porcentaje
        top = tk.Frame(content, bg=C['card'])
        top.pack(fill=tk.X, pady=(0, 6))
        tk.Label(top, text="PROGRESO", font=('Segoe UI', 8, 'bold'),
                 bg=C['card'], fg=C['text_secondary'],
                 letterSpacing=2 if False else 0).pack(side=tk.LEFT)
        pct = tk.Label(top, text="0%",
                       font=('Consolas', 11, 'bold'),
                       bg=C['card'], fg=C['accent_primary'])
        pct.pack(side=tk.RIGHT)

        # Etiqueta de estado
        status = tk.Label(content, text="⏳ Esperando inicio...",
                          font=ModernUI.FONTS['body'],
                          bg=C['card'], fg=C['text_primary'], anchor='w')
        status.pack(fill=tk.X, pady=(0, 6))

        # Progress bar delgada con canvas para mejor control visual
        pb_frame = tk.Frame(content, bg='#0d1a2e', height=6)
        pb_frame.pack(fill=tk.X, pady=(0, 4))
        pb_frame.pack_propagate(False)

        pb = ttk.Progressbar(pb_frame, mode='determinate', maximum=100,
                             style='Aspers.Horizontal.TProgressbar')
        pb.pack(fill=tk.BOTH, expand=True)

        # Detalle
        detail = tk.Label(content, text="",
                          font=ModernUI.FONTS['small'],
                          bg=C['card'], fg=C['text_muted'], anchor='w')
        detail.pack(fill=tk.X, pady=(2, 6))

        # Fila inferior: timer + recursos
        bottom = tk.Frame(content, bg=C['card'])
        bottom.pack(fill=tk.X)
        timer = tk.Label(bottom, text="⏱  00:00:00",
                         font=('Consolas', 9),
                         bg=C['card'], fg=C['accent_info'])
        timer.pack(side=tk.LEFT)
        resources = tk.Label(bottom, text="",
                             font=ModernUI.FONTS['small'],
                             bg=C['card'], fg=C['text_muted'])
        resources.pack(side=tk.RIGHT)

        return {
            'container': card,
            'status':    status,
            'progress':  pb,
            'detail':    detail,
            'timer':     timer,
            'resources': resources,
            'percent':   pct,
        }

    # ── Botones ──────────────────────────────────────────────────────────────
    @staticmethod
    def create_button(parent, text, command, style='primary', icon=''):
        C = ModernUI.COLORS
        label = f"{icon}  {text}" if icon else text

        if style == 'primary':
            bg = C['accent_primary'];    hv = C['accent_primary_hover']
            fg = '#000000';              px, py, fs = 28, 11, 11
        elif style == 'secondary':
            bg = C['bg_tertiary'];       hv = '#141c2f'
            fg = C['text_primary'];      px, py, fs = 20, 8, 9
        else:
            bg = C['bg_secondary'];      hv = C['bg_tertiary']
            fg = C['text_secondary'];    px, py, fs = 16, 6, 9

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
        btn.pack()
        btn.bind('<Enter>', lambda e: btn.config(bg=hv))
        btn.bind('<Leave>', lambda e: btn.config(bg=bg))
        return frame

    # ── Sección de resultados ────────────────────────────────────────────────
    @staticmethod
    def create_results_section(parent):
        C = ModernUI.COLORS

        outer = tk.Frame(parent, bg=C['bg_primary'])
        outer.pack(fill=tk.BOTH, expand=True, padx=18, pady=(0, 18))

        card = tk.Frame(outer, bg=C['card'])
        card.pack(fill=tk.BOTH, expand=True)
        tk.Frame(card, bg=C['accent_secondary'], height=1).pack(fill=tk.X)

        content = tk.Frame(card, bg=C['card'])
        content.pack(fill=tk.BOTH, expand=True, padx=18, pady=12)

        title = tk.Label(content, text="RESULTADOS",
                         font=('Segoe UI', 8, 'bold'),
                         bg=C['card'], fg=C['text_secondary'], anchor='w')
        title.pack(fill=tk.X, pady=(0, 8))

        ta = scrolledtext.ScrolledText(
            content, wrap=tk.WORD,
            font=ModernUI.FONTS['mono'],
            bg=C['bg_secondary'], fg=C['text_primary'],
            padx=14, pady=12,
            insertbackground=C['accent_primary'],
            selectbackground=C['bg_tertiary'],
            selectforeground=C['text_primary'],
            relief=tk.FLAT, bd=0, highlightthickness=0,
        )
        ta.pack(fill=tk.BOTH, expand=True)

        ta.tag_config('success', foreground=C['accent_secondary'],
                      font=(ModernUI.FONTS['mono'][0], ModernUI.FONTS['mono'][1], 'bold'))
        ta.tag_config('warning', foreground=C['accent_warning'],
                      font=(ModernUI.FONTS['mono'][0], ModernUI.FONTS['mono'][1], 'bold'))
        ta.tag_config('danger',  foreground=C['accent_danger'],
                      font=(ModernUI.FONTS['mono'][0], ModernUI.FONTS['mono'][1], 'bold'))
        ta.tag_config('info',    foreground=C['accent_info'],
                      font=(ModernUI.FONTS['mono'][0], ModernUI.FONTS['mono'][1], 'bold'))
        ta.tag_config('header',  foreground=C['text_primary'],
                      font=(ModernUI.FONTS['mono'][0], ModernUI.FONTS['mono'][1], 'bold'))

        return {'container': card, 'text': ta, 'title': title}
