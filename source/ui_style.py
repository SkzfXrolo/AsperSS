"""
Argus Scanner — UI Style v5 (Minimal × Eye Hybrid)
===================================================
Dark minimal base + warm copper accents + orbit progress animation.
Floating shields, clean typography, no heavy cards.

API pública (usada por main.py):
    apply_window_style, create_header, create_progress_section,
    create_completion_panel, create_button, create_results_section,
    set_status_badge, update_counter, update_canvas_bar,
    set_completion_state, COLORS, FONTS.
"""
import tkinter as tk
from tkinter import ttk, scrolledtext
import os, sys, math, random, ctypes, base64, io

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


class ModernUI:
    """Argus Scanner — Minimal × Eye Hybrid UI."""

    COLORS = {
        'bg_primary':     '#09090b',
        'bg_secondary':   '#0f0f11',
        'bg_card':        '#111113',
        'bg_hover':       '#1a1a1e',
        'text_primary':   '#f5f5f5',
        'text_secondary': '#a1a1aa',
        'text_muted':     '#3f3f46',
        'accent':         '#B87333',
        'accent_light':   '#E8A86F',
        'accent_hover':   '#D4915A',
        'accent_deep':    '#6B3A1D',
        'accent_glow':    '#FFC899',
        'green':          '#22c55e',
        'green_glow':     '#34D399',
        'amber':          '#FCD34D',
        'red':            '#f87171',
        'red_deep':       '#DC2626',
        'blue':           '#7DD3FC',
        'gold':           '#D4A017',
        'border':         '#1f1f23',
        'border_bright':  '#27272a',
        'separator':      '#18181b',
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

    # orbit animation
    _orbit_canvas = None
    _orbit_after_id = None
    _orbit_angle = 0.0
    _orbit_pct_text = None
    _orbit_pct_sign = None

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

    @staticmethod
    def _base_path():
        if getattr(sys, 'frozen', False):
            return sys._MEIPASS
        return os.path.dirname(os.path.abspath(__file__))

    # ══════════════════════════════════════════════════════════════════════
    #  FLOATING SHIELD BACKGROUND
    # ══════════════════════════════════════════════════════════════════════
    @classmethod
    def _create_floating_bg(cls, parent):
        C = cls.COLORS
        canvas = tk.Canvas(parent, bg=C['bg_primary'], highlightthickness=0, bd=0)
        canvas.place(x=0, y=0, relwidth=1.0, relheight=1.0)
        cls._bg_canvas = canvas

        b64 = _load_shield_b64()
        if not b64 or not _PIL_OK:
            return canvas

        try:
            raw = base64.b64decode(b64)
            base_img = Image.open(io.BytesIO(raw)).convert('RGBA')
        except Exception:
            return canvas

        cls._shield_images = []
        cls._shield_items = []

        sizes = [28, 34, 40, 48, 56]
        num_shields = 7

        def _make_ghost(img, alpha_factor):
            r, g, b, a = img.split()
            a = a.point(lambda p: int(p * alpha_factor))
            return Image.merge('RGBA', (r, g, b, a))

        for i in range(num_shields):
            sz = sizes[i % len(sizes)]
            alpha = random.uniform(0.03, 0.08)
            ghost = _make_ghost(base_img.resize((sz, sz), Image.LANCZOS), alpha)
            photo = ImageTk.PhotoImage(ghost)
            cls._shield_images.append(photo)

            x = random.randint(0, 620)
            y = random.randint(0, 480)
            vx = random.uniform(-0.2, 0.2)
            vy = random.uniform(-0.15, 0.15)
            if abs(vx) < 0.04:
                vx = 0.08
            if abs(vy) < 0.04:
                vy = 0.06

            item_id = canvas.create_image(x, y, image=photo, anchor='center')
            cls._shield_items.append({
                'id': item_id, 'x': float(x), 'y': float(y),
                'vx': vx, 'vy': vy, 'sz': sz,
            })

        def _animate():
            try:
                cw = canvas.winfo_width()
                ch = canvas.winfo_height()
                if cw < 10:
                    cw = 620
                if ch < 10:
                    ch = 480
                for s in cls._shield_items:
                    s['x'] += s['vx']
                    s['y'] += s['vy']
                    half = s['sz'] / 2
                    if s['x'] < -half:
                        s['x'] = cw + half
                    elif s['x'] > cw + half:
                        s['x'] = -half
                    if s['y'] < -half:
                        s['y'] = ch + half
                    elif s['y'] > ch + half:
                        s['y'] = -half
                    canvas.coords(s['id'], s['x'], s['y'])
                cls._bg_anim_id = canvas.after(50, _animate)
            except Exception:
                pass

        canvas.after(300, _animate)
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
                copper_colorref = ctypes.c_int(0x003373B8)
                ctypes.windll.dwmapi.DwmSetWindowAttribute(hwnd, 34, ctypes.byref(copper_colorref), ctypes.sizeof(copper_colorref))
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

        # Eye icon
        tk.Label(left, text="\U0001F441\uFE0F",
                 font=('Segoe UI', 11),
                 bg=C['bg_primary']).pack(side=tk.LEFT, padx=(0, 6))

        tk.Label(left, text="ARGUS",
                 font=('Segoe UI', 10, 'bold'),
                 bg=C['bg_primary'], fg=C['text_primary']).pack(side=tk.LEFT)

        tk.Label(left, text=" \u00b7 ",
                 font=('Segoe UI', 9),
                 bg=C['bg_primary'], fg=C['border_bright']).pack(side=tk.LEFT)

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
            _chrome_btn('\u2014', lambda: r.iconify())
            _chrome_btn('\u2715', lambda: r.destroy(), hover_fg=C['red'])

        sep = tk.Frame(hdr, bg=C['border'], height=1)
        sep.pack(fill=tk.X, side=tk.BOTTOM)

        try:
            cls.enhance_header(hdr, inner, right)
        except Exception:
            pass

        return hdr

    # ══════════════════════════════════════════════════════════════════════
    #  ORBIT PROGRESS INDICATOR
    # ══════════════════════════════════════════════════════════════════════
    @classmethod
    def _create_orbit(cls, parent, size=170):
        C = cls.COLORS
        canvas = tk.Canvas(parent, width=size, height=size,
                           bg=C['bg_primary'], highlightthickness=0, bd=0)

        cx, cy = size // 2, size // 2
        r1 = size // 2 - 4
        r2 = r1 - 20

        canvas.create_oval(cx - r1, cy - r1, cx + r1, cy + r1,
                           outline='#1a1a1e', width=1)
        canvas.create_oval(cx - r2, cy - r2, cx + r2, cy + r2,
                           outline='#111113', width=1)

        glow_r = 4
        glow_id = canvas.create_oval(0, 0, glow_r * 2, glow_r * 2,
                                     fill=C['accent'], outline='')
        glow_halo = canvas.create_oval(0, 0, glow_r * 4, glow_r * 4,
                                       fill='', outline=C['accent_deep'], width=1)

        pct_text = canvas.create_text(cx, cy - 2, text="0",
                                      font=('Segoe UI', 34, 'bold'),
                                      fill=C['text_primary'])
        pct_sign = canvas.create_text(cx + 30, cy + 8, text="%",
                                      font=('Segoe UI', 14),
                                      fill=C['text_muted'])

        cls._orbit_canvas = canvas
        cls._orbit_pct_text = pct_text
        cls._orbit_pct_sign = pct_sign

        cls._orbit_angle = 0.0

        def _spin():
            try:
                cls._orbit_angle += 0.04
                if cls._orbit_angle > 2 * math.pi:
                    cls._orbit_angle -= 2 * math.pi
                gx = cx + r1 * math.cos(cls._orbit_angle)
                gy = cy + r1 * math.sin(cls._orbit_angle)
                canvas.coords(glow_id,
                              gx - glow_r, gy - glow_r,
                              gx + glow_r, gy + glow_r)
                canvas.coords(glow_halo,
                              gx - glow_r * 2, gy - glow_r * 2,
                              gx + glow_r * 2, gy + glow_r * 2)
                cls._orbit_after_id = canvas.after(30, _spin)
            except Exception:
                pass

        canvas.after(200, _spin)
        return canvas

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

        if cls._bg_canvas:
            cls._bg_canvas.tk.call('lower', cls._bg_canvas._w)

        # Orbit indicator
        orbit = cls._create_orbit(outer, size=170)
        orbit.place(relx=0.5, rely=0.36, anchor='center')

        # Status text below orbit
        status = tk.Label(outer, text="Iniciando escaneo...",
                          font=('Segoe UI', 11),
                          bg=C['bg_primary'], fg=C['text_secondary'])
        status.place(relx=0.5, rely=0.59, anchor='center')
        cls._status_label_ref = status

        detail = tk.Label(outer, text="Preparando sistema...",
                          font=('Consolas', 9),
                          bg=C['bg_primary'], fg=C['text_muted'])
        detail.place(relx=0.5, rely=0.64, anchor='center')
        cls._detail_label_ref = detail

        # Thin progress bar
        bar_frame = tk.Frame(outer, bg=C['bg_primary'])
        bar_frame.place(relx=0.5, rely=0.74, anchor='center', width=260, height=20)

        bar_c = tk.Canvas(bar_frame, height=3,
                          bg=C['border'], highlightthickness=0, bd=0)
        bar_c.pack(fill=tk.X, pady=(0, 0))
        bar_c._shimmer_x = 0

        def _draw_bar(pct_val):
            bar_c.delete('bar')
            w = bar_c.winfo_width()
            if w < 2:
                return
            fw = max(0, int(w * pct_val / 100))
            if fw > 0:
                bar_c.create_rectangle(0, 0, fw, 3,
                                       fill=C['accent'], outline='', tags='bar')
                tip_w = min(16, fw)
                bar_c.create_rectangle(fw - tip_w, 0, fw, 3,
                                       fill=C['accent_light'], outline='', tags='bar')
            cls._update_orbit_pct(pct_val)

        bar_c._draw = _draw_bar

        # Timer + small percentage
        meta = tk.Frame(outer, bg=C['bg_primary'])
        meta.place(relx=0.5, rely=0.78, anchor='center', width=260)

        timer = tk.Label(meta, text="00:00:00",
                         font=('Consolas', 8),
                         bg=C['bg_primary'], fg=C['text_muted'])
        timer.pack(side=tk.LEFT)

        pct_lbl = tk.Label(meta, text="0%",
                           font=('Segoe UI', 8, 'bold'),
                           bg=C['bg_primary'], fg=C['text_muted'])
        pct_lbl.pack(side=tk.RIGHT)

        resources = tk.Label(outer, text="",
                             font=('Segoe UI', 7),
                             bg=C['bg_primary'], fg=C['text_muted'])
        resources.place(relx=0.5, rely=0.83, anchor='center')

        # Hidden counters (API compat)
        cls._counter_labels = {}
        for key in ('critical', 'suspicious', 'low', 'clean'):
            cls._counter_labels[key] = tk.Label(outer, text="",
                                                bg=C['bg_primary'], fg=C['bg_primary'])

        cls._risk_canvas = None
        cls._risk_label = None
        cls._cpu_bar_canvas = None
        cls._ram_bar_canvas = None
        cls._phase_dots_canvas = None

        # Cancel button (subtle, bottom-right)
        cancel_row = tk.Frame(outer, bg=C['bg_primary'])
        cancel_row.place(relx=1.0, rely=1.0, anchor='se', x=-18, y=-14)
        cancel_btn = tk.Button(cancel_row, text="\u2715 Cancelar",
                               font=('Segoe UI', 8),
                               bg=C['bg_primary'], fg=C['text_muted'],
                               activebackground=C['bg_hover'],
                               activeforeground=C['red'],
                               relief=tk.FLAT, bd=0, cursor='hand2',
                               padx=8, pady=3)
        cancel_btn.pack()

        # ttk bar compat
        pb = ttk.Progressbar(outer, mode='determinate', maximum=100,
                             style='Argus.Horizontal.TProgressbar')

        try:
            cls.create_sparkline(outer)
            cls.attach_files_counter(outer)
        except Exception:
            pass

        return {
            'container':  outer,
            'card':       outer,
            'status':     status,
            'progress':   pb,
            'detail':     detail,
            'timer':      timer,
            'resources':  resources,
            'percent':    pct_lbl,
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
        one_line = " ".join(str(text).split())
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
