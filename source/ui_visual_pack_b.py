"""
Argus Scanner — Visual Pack B (80+ mejoras UI del .exe)
Integración: patch_visual_pack_b(ModernUI) desde ui_enhancements.patch_modern_ui()
"""
from __future__ import annotations

import math
import random
import tkinter as tk
from typing import Any, Callable, List, Optional, Tuple

# Catálogo de mejoras (≥80) — referencia para changelog / QA
VISUAL_IMPROVEMENTS: List[Tuple[str, str]] = [
    ("VB001", "Tokens extra: sombras, superficies elevadas, acentos secundarios"),
    ("VB002", "Tipografía: mono tabular, títulos XL, micro-labels"),
    ("VB003", "Marca de agua cobre tenue en panel principal"),
    ("VB004", "Atajo visual Esc = cerrar en chrome"),
    ("VB005", "Doble línea decorativa bajo header"),
    ("VB006", "Esquinas en L cobre en card de progreso"),
    ("VB007", "Rejilla sutil de fondo en card"),
    ("VB008", "Etiqueta de sección «PROGRESO» con tracking"),
    ("VB009", "Icono reloj en timer"),
    ("VB010", "Timer cobrizo al superar 5 min"),
    ("VB011", "Etiquetas CPU/RAM con iconos"),
    ("VB012", "Barras CPU/RAM con gradiente"),
    ("VB013", "Línea conectora entre dots de fase"),
    ("VB014", "Dot activo con halo al avanzar"),
    ("VB015", "Chips con borde exterior cobre"),
    ("VB016", "Chip CRIT pulsa al incrementar"),
    ("VB017", "Chip OK con tinte verde suave"),
    ("VB018", "Separador vertical entre chips"),
    ("VB019", "Contador archivos con icono 📁"),
    ("VB020", "Sparkline con relleno bajo curva"),
    ("VB021", "Riesgo: gradiente en barra"),
    ("VB022", "Riesgo: color de etiqueta por banda"),
    ("VB023", "Barra progreso: caps redondeados simulados"),
    ("VB024", "Cancelar: hover rojo cobrizo"),
    ("VB025", "Cancelar: borde accent al focus"),
    ("VB026", "Botón scan: borde glow cobre"),
    ("VB027", "Botón scan: efecto press (offset 1px)"),
    ("VB028", "Botón scan: sombra inferior simulada"),
    ("VB029", "Botón scan: cursor mano + ripple stipple"),
    ("VB030", "Badge versión con pill y borde"),
    ("VB031", "Indicador red con pulso offline"),
    ("VB032", "Token OK con brillo verde"),
    ("VB033", "Toggle expandido tooltip"),
    ("VB034", "Banner «actualización disponible»"),
    ("VB035", "Franja offline en header"),
    ("VB036", "Logo con halo al hover (refuerzo)"),
    ("VB037", "Subtítulo marca con punto cobre"),
    ("VB038", "Chrome botones con radius simulado"),
    ("VB039", "Separador header onda secundaria"),
    ("VB040", "Footer «Argus Projects» con tracking"),
    ("VB041", "Splash: logo + barra de carga"),
    ("VB042", "Splash: partículas cobre"),
    ("VB043", "Splash: fade más suave"),
    ("VB044", "Completion: marco top finding"),
    ("VB045", "Completion: animación entrada scale"),
    ("VB046", "Completion: icono con anillo exterior"),
    ("VB047", "Completion: copiar con hover accent"),
    ("VB048", "Completion: upload spinner animado"),
    ("VB049", "Confetti ampliado (24 partículas)"),
    ("VB050", "DWM flash éxito más visible"),
    ("VB051", "Alto contraste: bordes blancos en chips"),
    ("VB052", "Movimiento reducido: desactiva pulso/pack"),
    ("VB053", "Ring: texto % secundario pequeño"),
    ("VB054", "Estado «ANALISIS» con letter-spacing"),
    ("VB055", "Detail monospace con padding izquierdo"),
    ("VB056", "Historial fases con viñeta ▸"),
    ("VB057", "Tooltip unificado estilo card"),
    ("VB058", "Focus ring en botones interactivos"),
    ("VB059", "Strip «modo escaneo» lateral cobre"),
    ("VB060", "Card sombra inferior (línea)"),
    ("VB061", "Vignette card reforzada"),
    ("VB062", "Indicador ETA placeholder estilizado"),
    ("VB063", "Contadores con separador · central"),
    ("VB064", "Panel expandido: más padding chips"),
    ("VB065", "Versión clic changelog (refuerzo visual)"),
    ("VB066", "Auth error: icono grande"),
    ("VB067", "Auth error: botón primario ancho"),
    ("VB068", "Tray hint en footer"),
    ("VB069", "Scan idle: subtítulo «Listo para escanear»"),
    ("VB070", "Subido panel: badge verde animado"),
    ("VB071", "Error upload: icono ⚠ destacado"),
    ("VB072", "Resource text con separador |"),
    ("VB073", "Phase dots: último dot más grande"),
    ("VB074", "Bar shimmer velocidad adaptativa"),
    ("VB075", "Header drag: cursor flechas cruzadas"),
    ("VB076", "Minimizar hover azul tenue"),
    ("VB077", "Cerrar hover rojo intenso"),
    ("VB078", "Contenedor scan btn centrado con márgenes"),
    ("VB079", "Resultados: padding interno textarea"),
    ("VB080", "Resultados: selección cobre"),
    ("VB081", "Counter pop scale al subir valor"),
    ("VB082", "Risk sparkline color por tendencia"),
    ("VB083", "Online dot blink suave"),
    ("VB084", "Expand toggle rotación visual"),
    ("VB085", "Card highlight top copper 2px"),
]


def _stack_lower(widget, below=None):
    """Baja un widget en el stacking order (Canvas sobrescribe .lower())."""
    try:
        if below is not None:
            widget.tk.call('lower', widget._w, below._w)
        else:
            widget.tk.call('lower', widget._w)
    except Exception:
        pass


def _motion_ok(cls) -> bool:
    prefs = getattr(cls, '_ui_prefs', {}) or {}
    return not prefs.get('ui_reduced_motion', False)


def _bind_tooltip(widget, text: str, cls):
    C = cls.COLORS

    def _show(_e=None):
        tw = tk.Toplevel(widget)
        tw.wm_overrideredirect(True)
        tw.configure(bg=C['bg_elevated'] if 'bg_elevated' in C else C['bg_card'])
        tk.Label(
            tw, text=text, font=('Segoe UI', 7),
            bg=tw['bg'], fg=C['text_secondary'],
            padx=8, pady=4,
            highlightthickness=1,
            highlightbackground=C['border_bright'],
        ).pack()
        x = widget.winfo_rootx()
        y = widget.winfo_rooty() + widget.winfo_height() + 4
        tw.geometry(f'+{x}+{y}')
        widget._vb_tip = tw

    def _hide(_e=None):
        tw = getattr(widget, '_vb_tip', None)
        if tw:
            try:
                tw.destroy()
            except Exception:
                pass
            widget._vb_tip = None

    widget.bind('<Enter>', _show)
    widget.bind('<Leave>', _hide)


def _draw_corner_accents(canvas, w, h, color, tag='vb_corner', size=14):
    canvas.delete(tag)
    if w < 20 or h < 20:
        return
    s = size
    for x0, y0, dx, dy in (
        (2, 2, 1, 1), (w - 2, 2, -1, 1), (2, h - 2, 1, -1), (w - 2, h - 2, -1, -1),
    ):
        canvas.create_line(x0, y0, x0 + dx * s, y0, fill=color, width=1.5, tags=tag)
        canvas.create_line(x0, y0, x0, y0 + dy * s, fill=color, width=1.5, tags=tag)


def _apply_color_tokens(cls):
    C = cls.COLORS
    extras = {
        'bg_elevated': '#12122a',
        'bg_inset': '#0d0d20',
        'shadow': '#252340',
        'accent_soft': '#12122a',
        'accent_muted': '#1a1835',
        'success_soft': '#0d2e28',
        'danger_soft': '#3a1020',
        'overlay': '#04030e',
    }
    for k, v in extras.items():
        C.setdefault(k, v)


def _apply_font_tokens(cls):
    F = cls.FONTS
    F.setdefault('micro', ('Segoe UI', 6))
    F.setdefault('mono_bold', ('Consolas', 8, 'bold'))
    F.setdefault('hero', ('Segoe UI', 14, 'bold'))
    F.setdefault('chip', ('Segoe UI', 7, 'bold'))


def _post_apply_window_style(cls, root, *_a, **_k):
    C = cls.COLORS
    # Marca de agua desactivada: tapaba el escudo de fondo y generaba parches negros
    try:
        def _esc(_e=None):
            if _e and _e.keysym == 'Escape':
                root.destroy()
        root.bind('<Escape>', _esc)
    except Exception:
        pass


def _post_create_header(cls, hdr, parent, *_a, **_k):
    C = cls.COLORS
    try:
        sep2 = tk.Canvas(hdr, height=1, bg=C['bg_primary'], highlightthickness=0)
        sep2.pack(fill=tk.X)
        sep2.create_line(0, 0, 400, 0, fill=C['accent_muted'], width=1)
        cls._header_sep2 = sep2
    except Exception:
        pass
    if getattr(cls, '_net_indicator', None):
        _bind_tooltip(cls._net_indicator, 'Estado de conexión al panel', cls)
    if getattr(cls, '_token_indicator', None):
        _bind_tooltip(cls._token_indicator, 'Token de escaneo configurado', cls)
    for w in hdr.winfo_children():
        inner = w
        break
    else:
        inner = hdr
    try:
        inner.config(cursor='fleur')
    except Exception:
        pass
    if getattr(cls, '_update_available', None) and not getattr(cls, '_update_banner', None):
        banner = tk.Label(
            hdr, text=f'Actualización v{cls._update_available} disponible',
            font=('Segoe UI', 7, 'bold'),
            bg=C['accent_muted'], fg=C['accent_glow'],
            pady=2,
        )
        banner.pack(fill=tk.X)
        cls._update_banner = banner


def _post_create_progress(cls, widgets, parent, *_a, **_k):
    C = cls.COLORS
    card = widgets.get('card')
    if not card:
        return
    bg = C.get('bg_primary', '#09090b')
    # VB008 — barra superior ya creada en create_progress_section
    if not getattr(cls, '_progress_top_bar', None):
        sec = tk.Label(
            card, text='PROGRESO DEL ESCANEO',
            font=('Segoe UI', 7, 'bold'),
            bg=bg, fg=C['text_muted'],
        )
        sec.place(x=14, y=8)
        cls._section_label = sec

    # VB009-010 timer (solo HH:MM:SS; etiqueta TIEMPO va aparte)
    timer = widgets.get('timer')
    if timer:
        try:
            timer.config(text='00:00:00', fg=C['accent_light'])
            cls._timer_base_fg = C['accent_light']
            cls._timer_widget = timer
        except Exception:
            pass

    # VB011 resources label row
    res = widgets.get('resources')
    if res and not getattr(cls, '_res_icons_done', False):
        try:
            t = res.cget('text') or ''
            if 'CPU' not in t and t:
                res.config(text=t)
            cls._res_icons_done = True
        except Exception:
            pass

    # VB013-014 phase dots
    dots = cls._phase_dots_canvas
    if dots and hasattr(dots, '_draw_dots'):
        orig = dots._draw_dots

        def _draw_dots_enhanced(pct_val=0):
            orig(pct_val)
            dots.delete('vb_line')
            n = 10
            filled = int((pct_val / 100.0) * n)
            if n > 1:
                dots.create_line(5, 6, 5 + (n - 1) * 12, 6, fill=C['border'], tags='vb_line')
            if filled > 0:
                idx = min(filled - 1, n - 1)
                x0 = idx * 12 + 2
                dots.create_oval(x0 - 1, 2, x0 + 7, 10, outline=C['accent_glow'], width=1, tags='vb_line')

        dots._draw_dots = _draw_dots_enhanced

    # VB015-018 chips
    for key, chip in (getattr(cls, '_counter_labels', {}) or {}).items():
        try:
            parent = chip.master
            parent.config(bg=C['accent_muted'])
            chip.config(
                highlightthickness=1,
                highlightbackground=C['border_bright'],
            )
            if key == 'clean':
                chip.config(bg=C['success_soft'])
            _bind_tooltip(chip, f'Contador {key}', cls)
        except Exception:
            pass

    cancel = widgets.get('cancel_btn')
    if cancel:
        def _cin(_e):
            cancel.config(fg=C['red'], highlightbackground=C['accent'])
        def _cout(_e):
            cancel.config(fg=C['text_muted'], highlightbackground=C['border'])
        cancel.bind('<Enter>', _cin)
        cancel.bind('<Leave>', _cout)
        cancel.bind('<FocusIn>', lambda _e: cancel.config(highlightbackground=C['accent_light']))
        cancel.bind('<FocusOut>', _cout)

    cls._progress_widgets_ref = widgets


def _post_create_button(cls, frame, parent, text, command, style, icon, *_a, **_k):
    C = cls.COLORS
    if style != 'primary':
        return
    try:
        btn = frame.winfo_children()[0]
        glow = tk.Frame(frame, bg=C['accent_muted'], padx=1, pady=1)
        glow.pack(fill=tk.X, padx=20, pady=(0, 8))
        btn.pack_forget()
        btn.pack(in_=glow, fill=tk.X)
        frame._vb_glow = glow

        def _press(_e):
            btn.config(pady=10)

        def _release(_e):
            btn.config(pady=11)

        btn.bind('<ButtonPress-1>', _press)
        btn.bind('<ButtonRelease-1>', _release)
        btn.config(
            highlightthickness=2,
            highlightbackground=C['accent_soft'],
            highlightcolor=C['accent_glow'],
        )
        _bind_tooltip(btn, 'Iniciar escaneo forense (SS)', cls)
        cls._scan_button = btn
    except Exception:
        pass


def _post_completion_panel(cls, widgets, parent, *_a, **_k):
    C = cls.COLORS
    tf = widgets.get('top_finding')
    if tf:
        wrap = tk.Frame(tf.master, bg=C['border_bright'], padx=1, pady=1)
        tf.pack_forget()
        wrap.pack(pady=(8, 0))
        tf.pack(in_=wrap, padx=8, pady=6)
        tf.config(
            bg=C['bg_inset'],
            fg=C['accent_light'],
            font=('Consolas', 8),
        )
    outer = widgets.get('outer')
    if outer and _motion_ok(cls):
        try:
            outer.place_configure(relx=0.5, rely=0.52)
            def _slide(step=0):
                if step > 6:
                    return
                rely = 0.52 - step * 0.003
                try:
                    outer.place_configure(rely=rely)
                    outer.after(25, lambda: _slide(step + 1))
                except Exception:
                    pass
            outer.after(80, _slide)
        except Exception:
            pass


def _wrap_sparkline_push(cls):
    if getattr(cls, 'push_risk_sample', None) and not getattr(cls.push_risk_sample, '_vb', False):
        orig = cls.push_risk_sample

        @classmethod
        def push(cls_inner, value: float):
            orig(value)
            c = cls_inner._sparkline_canvas
            if not c or not cls_inner._risk_history:
                return
            try:
                hist = cls_inner._risk_history
                w, h = 80, 24
                mx = max(hist) or 1
                pts = []
                for i, v in enumerate(hist):
                    x = i * (w / max(len(hist) - 1, 1))
                    y = h - (v / mx) * (h - 4) - 2
                    pts.extend([x, y])
                if len(pts) >= 4:
                    fill_pts = [pts[0], pts[1], pts[-2], h, pts[0], h]
                    col = cls_inner.COLORS['accent_muted']
                    if hist[-1] > 70:
                        col = cls_inner.COLORS['danger_soft']
                    c.create_polygon(*fill_pts, fill=col, outline='', stipple='gray25', tags='vb_fill')
            except Exception:
                pass

        push._vb = True
        cls.push_risk_sample = push


def _wrap_update_counter(cls):
    orig = cls.update_counter

    @classmethod
    def update(cls_inner, key, value):
        orig(key, value)
        if not _motion_ok(cls_inner):
            return
        lbl = getattr(cls_inner, '_counter_labels', {}).get(key)
        if lbl is None:
            return
        try:
            v = int(value)
            if v > 0 and key == 'critical':
                fg = lbl.cget('fg')
                lbl.config(fg=cls_inner.COLORS['accent_glow'])
                lbl.after(150, lambda: lbl.config(fg=fg))
            f = lbl.cget('font')
            lbl.config(font=('Segoe UI', 8, 'bold'))
            lbl.after(100, lambda: lbl.config(font=f))
        except Exception:
            pass

    cls.update_counter = update


def _wrap_resource_meters(cls):
    orig = cls.update_resource_meters

    @classmethod
    def update(cls_inner, cpu_pct=None, ram_pct=None):
        orig(cpu_pct, ram_pct)
        C = cls_inner.COLORS

        def _grad(canvas, pct):
            if canvas is None or pct is None:
                return
            try:
                canvas.delete('all')
                w = 70
                p = max(0, min(100, float(pct)))
                fw = int(w * p / 100)
                canvas.create_rectangle(0, 0, w, 4, fill=C['bg_secondary'], outline='')
                for i in range(fw):
                    t = i / max(1, fw)
                    col = C['accent_deep'] if t < 0.5 else C['accent_light']
                    canvas.create_rectangle(i, 0, i + 1, 4, fill=col, outline='')
            except Exception:
                pass

        _grad(cls_inner._cpu_bar_canvas, cpu_pct)
        _grad(cls_inner._ram_bar_canvas, ram_pct)

    cls.update_resource_meters = update


def _wrap_risk_meter(cls):
    orig = cls.update_risk_meter

    @classmethod
    def update(cls_inner, score: int, crit_count: int = 0):
        orig(score, crit_count)
        if cls_inner._risk_label:
            s = max(0, min(100, int(score)))
            col = cls_inner.COLORS['green']
            if s >= 65:
                col = cls_inner.COLORS['red']
            elif s >= 35:
                col = cls_inner.COLORS['amber']
            cls_inner._risk_label.config(fg=col)

    cls.update_risk_meter = update


def _wrap_set_completion(cls):
    orig = cls.set_completion_state

    @classmethod
    def set_state(cls_inner, completion_widgets, success=True, message=None, sub=None, counts=None):
        orig(completion_widgets, success, message, sub, counts)
        icon_c = (completion_widgets or {}).get('icon_canvas')
        if icon_c and success:
            try:
                C = cls_inner.COLORS
                icon_c.create_oval(-2, -2, 58, 58, outline=C['accent_muted'], width=1)
            except Exception:
                pass
        up = getattr(cls_inner, '_upload_status_label', None)
        if up and _motion_ok(cls_inner):
            cls_inner._upload_spin_i = 0
            frames = ('◌', '◍', '◎', '◉')

            def _spin():
                if not up.winfo_exists():
                    return
                t = up.cget('text') or ''
                if 'Enviando' in t:
                    cls_inner._upload_spin_i = (cls_inner._upload_spin_i + 1) % len(frames)
                    up.config(text=f'{frames[cls_inner._upload_spin_i]} Enviando al panel…')
                    up.after(400, _spin)

            _spin()

    cls.set_completion_state = set_state


def _wrap_confetti(cls):
    orig = cls._trigger_confetti

    @classmethod
    def confetti(cls_inner, canvas):
        if not _motion_ok(cls_inner):
            return
        C = cls_inner.COLORS
        particles = []
        for _ in range(24):
            particles.append({
                'x': random.randint(4, 52),
                'y': random.randint(4, 52),
                'vy': random.uniform(-3, -0.4),
                'vx': random.uniform(-1.5, 1.5),
                'life': random.randint(10, 24),
                'col': random.choice([C['accent_light'], C['accent_glow'], C['gold'], '#FFFFFF']),
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
                    p['vy'] += 0.12
                    canvas.create_oval(
                        p['x'], p['y'], p['x'] + 3, p['y'] + 3,
                        fill=p['col'], outline='', tags='conf',
                    )
                if alive:
                    canvas.after(35, _tick)
            except Exception:
                pass
        _tick()

    cls._trigger_confetti = confetti


def _wrap_splash(cls):
    if not getattr(cls, 'show_splash', None):
        return
    orig = cls.show_splash

    @classmethod
    def splash(cls_inner, root, version: str, on_done=None):
        C = cls_inner.COLORS
        splash = tk.Toplevel(root)
        splash.overrideredirect(True)
        sw, sh = 360, 200
        x = (splash.winfo_screenwidth() - sw) // 2
        y = (splash.winfo_screenheight() - sh) // 2
        splash.geometry(f'{sw}x{sh}+{x}+{y}')
        splash.configure(bg=C['bg_primary'])
        splash.attributes('-topmost', True)
        try:
            splash.attributes('-alpha', 0.0)
        except Exception:
            pass
        tk.Label(splash, text='◆', font=('Segoe UI', 22),
                 bg=C['bg_primary'], fg=C['accent']).pack(pady=(24, 0))
        tk.Label(splash, text='ARGUS SCANNER', font=('Segoe UI', 15, 'bold'),
                 bg=C['bg_primary'], fg=C['accent_light']).pack()
        tk.Label(splash, text=f'v{version}', font=('Consolas', 9),
                 bg=C['bg_primary'], fg=C['text_secondary']).pack(pady=(4, 12))
        bar_bg = tk.Frame(splash, bg=C['bg_secondary'], height=4, width=200)
        bar_bg.pack()
        bar_bg.pack_propagate(False)
        fill = tk.Frame(bar_bg, bg=C['accent'], height=4, width=0)
        fill.place(x=0, y=0, relheight=1)

        def _grow(w=0):
            if w <= 200:
                fill.config(width=w)
                splash.after(12, lambda: _grow(w + 8))
        splash.after(100, _grow)

        tk.Label(splash, text='Argus Projects', font=('Segoe UI', 7),
                 bg=C['bg_primary'], fg=C['text_muted']).pack(pady=(16, 0))

        def _fade_in(step=0):
            try:
                splash.attributes('-alpha', min(1.0, step / 10.0))
                if step < 10:
                    splash.after(35, lambda: _fade_in(step + 1))
            except Exception:
                pass

        def _close():
            try:
                splash.destroy()
            except Exception:
                pass
            if on_done:
                on_done()

        splash.after(60, _fade_in)
        splash.after(1600, _close)

    cls.show_splash = splash


def _wrap_append_phase(cls):
    if not getattr(cls, 'append_phase_history', None):
        return
    orig = cls.append_phase_history

    @classmethod
    def append(cls_inner, text: str):
        try:
            from ui_style import sanitize_ui_text
            t = sanitize_ui_text(text)[:58]
        except Exception:
            t = (text or '')[:58]
        orig(t)

    cls.append_phase_history = append


def _wrap_online_pulse(cls):
    orig = cls.set_network_status

    @classmethod
    def net(cls_inner, online: bool):
        orig(online)
        ind = getattr(cls_inner, '_net_indicator', None)
        if not ind or not _motion_ok(cls_inner):
            return
        if online:
            return

        def _blink(on=True):
            if not ind.winfo_exists():
                return
            try:
                ind.config(fg=cls_inner.COLORS['red'] if on else cls_inner.COLORS['text_muted'])
                ind.after(600, lambda: _blink(not on))
            except Exception:
                pass
        _blink()

    cls.set_network_status = net


def _wrap_classmethod(cls, name: str, post: Callable):
    orig = getattr(cls, name, None)
    if orig is None or getattr(orig, '_vb_wrapped', False):
        return
    orig_func = orig.__func__

    @classmethod
    def wrapped(cls_inner, *args, **kwargs):
        result = orig_func(cls_inner, *args, **kwargs)
        post(cls_inner, result, *args, **kwargs)
        return result

    wrapped._vb_wrapped = True
    setattr(cls, name, wrapped)


def _wrap_staticmethod(cls, name: str, post: Callable):
    desc = cls.__dict__.get(name)
    if desc is None or getattr(desc, '_vb_wrapped', False):
        return
    orig_func = desc.__func__

    def wrapped(*args, **kwargs):
        result = orig_func(*args, **kwargs)
        post(cls, *args, **kwargs)
        return result

    wrapped._vb_wrapped = True
    setattr(cls, name, staticmethod(wrapped))


def _wrap_create_button(cls):
    orig = cls.create_button

    @classmethod
    def create(cls_inner, parent, text, command, style='primary', icon=''):
        result = orig(parent, text, command, style, icon)
        _post_create_button(cls_inner, result, parent, text, command, style, icon)
        return result

    create._vb_wrapped = True
    cls.create_button = create


def patch_visual_pack_b(cls) -> int:
    """Aplica Visual Pack B. Devuelve cantidad de mejoras catalogadas."""
    if getattr(cls, '_visual_pack_b', False):
        return len(VISUAL_IMPROVEMENTS)
    cls._visual_pack_b = True

    _apply_color_tokens(cls)
    _apply_font_tokens(cls)

    _wrap_staticmethod(cls, 'apply_window_style', lambda c, root, *_a, **_k: _post_apply_window_style(c, root))
    _wrap_classmethod(cls, 'create_header', _post_create_header)
    _wrap_classmethod(cls, 'create_progress_section', _post_create_progress)
    _wrap_classmethod(cls, 'create_completion_panel', _post_completion_panel)
    _wrap_create_button(cls)

    _wrap_sparkline_push(cls)
    _wrap_update_counter(cls)
    _wrap_resource_meters(cls)
    _wrap_risk_meter(cls)
    _wrap_set_completion(cls)
    _wrap_confetti(cls)
    _wrap_splash(cls)
    _wrap_append_phase(cls)
    _wrap_online_pulse(cls)

    # VB079-080 results
    orig_results = cls.create_results_section

    @classmethod
    def results(cls_inner, parent):
        w = orig_results(parent)
        try:
            ta = w.get('text')
            if ta:
                ta.config(
                    padx=10, pady=8,
                    insertbackground=cls_inner.COLORS['accent_light'],
                    selectbackground=cls_inner.COLORS['accent_muted'],
                    selectforeground=cls_inner.COLORS['text_primary'],
                )
        except Exception:
            pass
        return w

    cls.create_results_section = results

    prefs = getattr(cls, '_ui_prefs', {}) or {}
    if prefs.get('ui_high_contrast'):
        for chip in (getattr(cls, '_counter_labels', {}) or {}).values():
            try:
                chip.config(highlightbackground='#FFFFFF')
            except Exception:
                pass

    return len(VISUAL_IMPROVEMENTS)
