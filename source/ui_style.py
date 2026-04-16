import tkinter as tk
from tkinter import ttk, scrolledtext

class ModernUI:
    """Sistema de estilos moderno minimalista para Aspers Projects - Diseño sorprendente y funcional"""
    
    COLORS = {
        # Fondos sólidos sin transparencia
        'bg_primary': '#0d1117',
        'bg_secondary': '#161b22',
        'bg_tertiary': '#21262d',
        'card': '#161b22',
        
        # Textos
        'text_primary': '#f0f6fc',
        'text_secondary': '#8b949e',
        'text_muted': '#6e7681',
        
        # Acentos vibrantes
        'accent_primary': '#238636',      # Verde principal
        'accent_primary_hover': '#2ea043',
        'accent_secondary': '#1f6feb',     # Azul secundario
        'accent_warning': '#d29922',
        'accent_danger': '#f85149',
        'accent_info': '#58a6ff',
        
        # Bordes y separadores
        'border': '#30363d',
        'border_light': '#21262d',
    }
    
    FONTS = {
        'title': ('Segoe UI', 24, 'bold'),
        'subtitle': ('Segoe UI', 9),
        'heading': ('Segoe UI', 11, 'bold'),
        'body': ('Segoe UI', 9),
        'body_bold': ('Segoe UI', 9, 'bold'),
        'small': ('Segoe UI', 8),
        'mono': ('Consolas', 8),
        'button': ('Segoe UI', 9, 'bold'),
    }
    
    @staticmethod
    def apply_window_style(root):
        """Aplica estilo general - Sin transparencias, completamente opaco"""
        root.title("Aspers Projects - Security Scanner Pro")
        
        # Detectar resolución
        screen_width = root.winfo_screenwidth()
        
        if screen_width <= 1366:
            width, height = 1150, 650
            min_width, min_height = 950, 550
        elif screen_width <= 1920:
            width, height = 1350, 800
            min_width, min_height = 1150, 650
        else:
            width, height = 1550, 900
            min_width, min_height = 1350, 800
        
        root.geometry(f"{width}x{height}")
        root.minsize(min_width, min_height)
        root.configure(bg=ModernUI.COLORS['bg_primary'])
        
        # Asegurar que NO haya transparencia
        try:
            root.attributes('-alpha', 1.0)  # Completamente opaco
        except:
            pass
    
    @staticmethod
    def create_header(parent):
        """Header minimalista y compacto"""
        header = tk.Frame(parent, bg=ModernUI.COLORS['bg_secondary'], height=90)
        header.pack(fill=tk.X)
        header.pack_propagate(False)
        
        # Borde inferior sutil
        border = tk.Frame(header, bg=ModernUI.COLORS['accent_secondary'], height=1)
        border.pack(fill=tk.X, side=tk.BOTTOM)
        
        # Contenido compacto
        content = tk.Frame(header, bg=ModernUI.COLORS['bg_secondary'])
        content.pack(fill=tk.BOTH, expand=True, padx=20, pady=12)
        
        # Título y subtítulo en línea horizontal para ahorrar espacio
        title_row = tk.Frame(content, bg=ModernUI.COLORS['bg_secondary'])
        title_row.pack(fill=tk.X)
        
        title_label = tk.Label(
            title_row,
            text="ASPERS PROJECTS",
            font=ModernUI.FONTS['title'],
            bg=ModernUI.COLORS['bg_secondary'],
            fg=ModernUI.COLORS['text_primary'],
            anchor='w'
        )
        title_label.pack(side=tk.LEFT)
        
        # Badge inline
        badge = tk.Label(
            title_row,
            text="🟢 READY",
            font=ModernUI.FONTS['small'],
            bg=ModernUI.COLORS['accent_primary'],
            fg='#ffffff',
            padx=8,
            pady=2
        )
        badge.pack(side=tk.RIGHT, padx=(10, 0))
        
        # Subtítulo compacto
        subtitle = tk.Label(
            content,
            text="Security Scanner Pro • Advanced Anti-Bypass Detection",
            font=ModernUI.FONTS['subtitle'],
            bg=ModernUI.COLORS['bg_secondary'],
            fg=ModernUI.COLORS['text_secondary'],
            anchor='w'
        )
        subtitle.pack(fill=tk.X, pady=(4, 0))
        
        return header
    
    @staticmethod
    def create_progress_section(parent):
        """Sección de progreso ultra compacta"""
        container = tk.Frame(parent, bg=ModernUI.COLORS['bg_primary'])
        container.pack(fill=tk.X, padx=15, pady=(10, 8))
        
        # Card minimalista
        card = tk.Frame(container, bg=ModernUI.COLORS['card'], relief=tk.FLAT, bd=0)
        card.pack(fill=tk.BOTH, expand=True)
        
        # Borde superior fino
        border = tk.Frame(card, bg=ModernUI.COLORS['accent_secondary'], height=1)
        border.pack(fill=tk.X)
        
        # Contenido compacto
        content = tk.Frame(card, bg=ModernUI.COLORS['card'])
        content.pack(fill=tk.BOTH, expand=True, padx=15, pady=12)
        
        # Header en una línea
        header = tk.Frame(content, bg=ModernUI.COLORS['card'])
        header.pack(fill=tk.X, pady=(0, 8))
        
        title = tk.Label(
            header,
            text="📊 Progress",
            font=ModernUI.FONTS['heading'],
            bg=ModernUI.COLORS['card'],
            fg=ModernUI.COLORS['text_primary'],
            anchor='w'
        )
        title.pack(side=tk.LEFT)
        
        percent = tk.Label(
            header,
            text="0%",
            font=('Segoe UI', 11, 'bold'),
            bg=ModernUI.COLORS['card'],
            fg=ModernUI.COLORS['accent_info'],
            anchor='e'
        )
        percent.pack(side=tk.RIGHT)
        
        # Estado compacto
        status = tk.Label(
            content,
            text="⏳ Waiting...",
            font=ModernUI.FONTS['body'],
            bg=ModernUI.COLORS['card'],
            fg=ModernUI.COLORS['text_secondary'],
            anchor='w'
        )
        status.pack(fill=tk.X, pady=(0, 8))
        
        # Barra de progreso delgada
        progress_frame = tk.Frame(content, bg=ModernUI.COLORS['card'])
        progress_frame.pack(fill=tk.X, pady=(0, 6))
        
        style = ttk.Style()
        style.theme_use('clam')
        style.configure(
            "Aspers.Horizontal.TProgressbar",
            background=ModernUI.COLORS['accent_secondary'],
            troughcolor=ModernUI.COLORS['bg_tertiary'],
            borderwidth=0,
            lightcolor=ModernUI.COLORS['accent_secondary'],
            darkcolor=ModernUI.COLORS['accent_secondary'],
            thickness=12  # Muy delgada
        )
        
        progress_bar = ttk.Progressbar(
            progress_frame,
            mode='determinate',
            length=400,
            maximum=100,
            style="Aspers.Horizontal.TProgressbar"
        )
        progress_bar.pack(fill=tk.X)
        
        # Detalle compacto
        detail = tk.Label(
            content,
            text="",
            font=ModernUI.FONTS['small'],
            bg=ModernUI.COLORS['card'],
            fg=ModernUI.COLORS['text_muted'],
            anchor='w'
        )
        detail.pack(fill=tk.X, pady=(0, 6))
        
        # Info en una línea
        info_row = tk.Frame(content, bg=ModernUI.COLORS['card'])
        info_row.pack(fill=tk.X)
        
        timer = tk.Label(
            info_row,
            text="⏱️ 00:00:00",
            font=ModernUI.FONTS['small'],
            bg=ModernUI.COLORS['card'],
            fg=ModernUI.COLORS['accent_info'],
            anchor='w'
        )
        timer.pack(side=tk.LEFT)
        
        resources = tk.Label(
            info_row,
            text="",
            font=ModernUI.FONTS['small'],
            bg=ModernUI.COLORS['card'],
            fg=ModernUI.COLORS['text_muted'],
            anchor='e'
        )
        resources.pack(side=tk.RIGHT)
        
        return {
            'container': card,
            'status': status,
            'progress': progress_bar,
            'detail': detail,
            'timer': timer,
            'resources': resources,
            'percent': percent
        }
    
    @staticmethod
    def create_button(parent, text, command, style='primary', icon=''):
        """Botones minimalistas y compactos - MUY pequeños"""
        button_frame = tk.Frame(parent, bg=ModernUI.COLORS['bg_primary'])
        
        if style == 'primary':
            bg = ModernUI.COLORS['accent_primary']
            hover = ModernUI.COLORS['accent_primary_hover']
            fg = '#ffffff'
            padx, pady = 20, 8  # MUY compacto
            font_size = 9
        elif style == 'secondary':
            bg = ModernUI.COLORS['bg_tertiary']
            hover = ModernUI.COLORS['border']
            fg = ModernUI.COLORS['text_primary']
            padx, pady = 15, 6  # MUY compacto
            font_size = 8
        else:
            bg = ModernUI.COLORS['bg_secondary']
            hover = ModernUI.COLORS['bg_tertiary']
            fg = ModernUI.COLORS['text_secondary']
            padx, pady = 12, 5
            font_size = 8
        
        button = tk.Button(
            button_frame,
            text=f"{icon} {text}" if icon else text,
            command=command,
            bg=bg,
            fg=fg,
            font=(ModernUI.FONTS['button'][0], font_size, ModernUI.FONTS['button'][2]),
            padx=padx,
            pady=pady,
            relief=tk.FLAT,
            bd=0,
            cursor='hand2',
            activebackground=hover,
            activeforeground=fg,
            borderwidth=0,
            highlightthickness=0
        )
        button.pack()
        
        # Hover simple
        def on_enter(e):
            button.config(bg=hover)
        def on_leave(e):
            button.config(bg=bg)
        
        button.bind('<Enter>', on_enter)
        button.bind('<Leave>', on_leave)
        
        return button_frame
    
    @staticmethod
    def create_results_section(parent):
        """Sección de resultados compacta"""
        container = tk.Frame(parent, bg=ModernUI.COLORS['bg_primary'])
        container.pack(fill=tk.BOTH, expand=True, padx=15, pady=(0, 15))
        
        # Card minimalista
        card = tk.Frame(container, bg=ModernUI.COLORS['card'], relief=tk.FLAT, bd=0)
        card.pack(fill=tk.BOTH, expand=True)
        
        # Borde superior fino
        border = tk.Frame(card, bg=ModernUI.COLORS['accent_secondary'], height=1)
        border.pack(fill=tk.X)
        
        # Contenido compacto
        content = tk.Frame(card, bg=ModernUI.COLORS['card'])
        content.pack(fill=tk.BOTH, expand=True, padx=15, pady=12)
        
        # Título compacto
        title = tk.Label(
            content,
            text="📋 Results",
            font=ModernUI.FONTS['heading'],
            bg=ModernUI.COLORS['card'],
            fg=ModernUI.COLORS['text_primary'],
            anchor='w'
        )
        title.pack(fill=tk.X, pady=(0, 8))
        
        # Área de texto compacta
        text_area = scrolledtext.ScrolledText(
            content,
            wrap=tk.WORD,
            font=ModernUI.FONTS['mono'],
            bg=ModernUI.COLORS['bg_secondary'],
            fg=ModernUI.COLORS['text_primary'],
            padx=12,
            pady=12,
            insertbackground=ModernUI.COLORS['text_primary'],
            selectbackground=ModernUI.COLORS['accent_secondary'],
            selectforeground=ModernUI.COLORS['text_primary'],
            relief=tk.FLAT,
            bd=0,
            highlightthickness=0
        )
        text_area.pack(fill=tk.BOTH, expand=True)
        
        # Tags de color
        text_area.tag_config("success", foreground=ModernUI.COLORS['accent_primary'], font=(ModernUI.FONTS['mono'][0], ModernUI.FONTS['mono'][1], "bold"))
        text_area.tag_config("warning", foreground=ModernUI.COLORS['accent_warning'], font=(ModernUI.FONTS['mono'][0], ModernUI.FONTS['mono'][1], "bold"))
        text_area.tag_config("danger", foreground=ModernUI.COLORS['accent_danger'], font=(ModernUI.FONTS['mono'][0], ModernUI.FONTS['mono'][1], "bold"))
        text_area.tag_config("info", foreground=ModernUI.COLORS['accent_info'], font=(ModernUI.FONTS['mono'][0], ModernUI.FONTS['mono'][1], "bold"))
        text_area.tag_config("header", foreground=ModernUI.COLORS['text_primary'], font=(ModernUI.FONTS['mono'][0], ModernUI.FONTS['mono'][1], "bold"))
        
        return {
            'container': card,
            'text': text_area,
            'title': title
        }
