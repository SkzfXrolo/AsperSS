"""
Argus Scanner — Personalización beta (módulos + UI).
Ventana accesible con Ctrl+Shift+M o desde el header.
"""
import json
import tkinter as tk
from tkinter import ttk, messagebox

try:
    from config.scanner_custom import load_scanner_custom, _config_path
except ImportError:
    def load_scanner_custom():
        return {}
    def _config_path():
        return 'scanner_custom.json'


def _module_catalog():
    try:
        from scan_modules.novel_surfaces import NOVEL_MODULES
        from scan_modules.executor import MINING_MODULES
    except ImportError:
        return []
    out = []
    for mod_id, label, _fn in NOVEL_MODULES:
        cat = 'forensic' if mod_id.startswith('forensic_') else (
            'pkg' if mod_id.startswith('pkg_') else 'custom')
        out.append((mod_id, label, cat))
    try:
        for mod_id, label, _fn in MINING_MODULES:
            out.append((mod_id, label, 'mining'))
    except Exception:
        pass
    return out


def open_beta_settings(parent, colors=None):
    """Abre ventana de personalización beta."""
    C = colors or {
        'bg_primary': '#04030e',
        'text_primary': '#ECEDFF',
        'text_secondary': '#A6A8D0',
        'accent': '#8b7bff',
        'accent_light': '#b9a7ff',
        'border': '#2a2848',
    }
    custom = load_scanner_custom()
    mods_state = dict((custom.get('modules') or {}))
    ui_state = dict((custom.get('ui') or {}))
    perf = dict((custom.get('performance') or {}))

    win = tk.Toplevel(parent)
    win.title('Argus — Personalización (beta)')
    win.geometry('520x580')
    win.configure(bg=C['bg_primary'])
    win.transient(parent)
    win.grab_set()

    hdr = tk.Frame(win, bg=C['bg_primary'])
    hdr.pack(fill=tk.X, padx=16, pady=(14, 8))
    tk.Label(hdr, text='Personalización v1.7',
             font=('Segoe UI', 13, 'bold'), bg=C['bg_primary'], fg=C['text_primary']).pack(anchor='w')
    tk.Label(hdr, text='Activa o desactiva módulos del pack extendido. Los cambios se guardan en AppData.',
             font=('Segoe UI', 9), bg=C['bg_primary'], fg=C['text_secondary'], wraplength=480, justify='left').pack(anchor='w')

    nb = ttk.Notebook(win)
    nb.pack(fill=tk.BOTH, expand=True, padx=12, pady=8)

    tab_mod = tk.Frame(nb, bg=C['bg_primary'])
    tab_ui = tk.Frame(nb, bg=C['bg_primary'])
    nb.add(tab_mod, text='  Módulos  ')
    nb.add(tab_ui, text='  Visual  ')

    canvas = tk.Canvas(tab_mod, bg=C['bg_primary'], highlightthickness=0)
    scroll = ttk.Scrollbar(tab_mod, orient='vertical', command=canvas.yview)
    inner = tk.Frame(canvas, bg=C['bg_primary'])
    inner.bind('<Configure>', lambda e: canvas.configure(scrollregion=canvas.bbox('all')))
    canvas.create_window((0, 0), window=inner, anchor='nw')
    canvas.configure(yscrollcommand=scroll.set)
    canvas.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
    scroll.pack(side=tk.RIGHT, fill=tk.Y)

    checks = {}
    catalog = _module_catalog()
    by_cat = {'mining': [], 'extended': []}
    for mod_id, label, cat in catalog:
        by_cat.setdefault(cat, []).append((mod_id, label))

    def _section(title, items):
        tk.Label(inner, text=title, font=('Segoe UI', 10, 'bold'),
                 bg=C['bg_primary'], fg=C['accent_light']).pack(anchor='w', padx=8, pady=(12, 4))
        for mod_id, label in items:
            var = tk.BooleanVar(value=mods_state.get(mod_id, True))
            checks[mod_id] = var
            row = tk.Frame(inner, bg=C['bg_primary'])
            row.pack(fill=tk.X, padx=12, pady=2)
            tk.Checkbutton(row, text=f'{mod_id} — {label}', variable=var,
                           bg=C['bg_primary'], fg=C['text_secondary'],
                           selectcolor=C['bg_primary'], activebackground=C['bg_primary'],
                           font=('Segoe UI', 9), anchor='w').pack(anchor='w')

    _section('Minado automático (3)', by_cat.get('mining', []))
    _section('Scanners pkg (28)', by_cat.get('pkg', []))
    _section('SS Forensics (28)', by_cat.get('forensic', []))
    _section('Superficies nuevas (30)', by_cat.get('custom', []))

    tk.Label(tab_ui, text='Tema', font=('Segoe UI', 10, 'bold'),
             bg=C['bg_primary'], fg=C['text_primary']).pack(anchor='w', padx=16, pady=(16, 6))
    theme_var = tk.StringVar(value=ui_state.get('theme', 'cosmic'))
    for t in ('cosmic', 'classic', 'minimal'):
        tk.Radiobutton(tab_ui, text=t.capitalize(), variable=theme_var, value=t,
                       bg=C['bg_primary'], fg=C['text_secondary']).pack(anchor='w', padx=24)
    splash_var = tk.BooleanVar(value=ui_state.get('show_splash', True))
    wordmark_var = tk.BooleanVar(value=ui_state.get('show_wordmark', True))
    tk.Checkbutton(tab_ui, text='Mostrar splash al iniciar', variable=splash_var,
                   bg=C['bg_primary'], fg=C['text_secondary']).pack(anchor='w', padx=16, pady=8)
    tk.Checkbutton(tab_ui, text='Mostrar wordmark ARGUS', variable=wordmark_var,
                   bg=C['bg_primary'], fg=C['text_secondary']).pack(anchor='w', padx=16)

    tk.Label(tab_ui, text='Rendimiento del pack', font=('Segoe UI', 10, 'bold'),
             bg=C['bg_primary'], fg=C['text_primary']).pack(anchor='w', padx=16, pady=(20, 6))
    pool_var = tk.StringVar(value=str(perf.get('module_pool_size', 6)))
    tk.Label(tab_ui, text='Hilos paralelos', bg=C['bg_primary'], fg=C['text_secondary']).pack(anchor='w', padx=16)
    tk.Entry(tab_ui, textvariable=pool_var, width=8).pack(anchor='w', padx=16, pady=4)

    def _save():
        new_mods = {mid: var.get() for mid, var in checks.items()}
        data = {
            'beta_customization': True,
            'version': '1.7.0',
            'modules': new_mods,
            'ui': {
                'theme': theme_var.get(),
                'show_splash': splash_var.get(),
                'show_wordmark': wordmark_var.get(),
            },
            'performance': {
                'module_pool_size': max(2, min(12, int(pool_var.get() or 6))),
                'module_default_timeout_sec': perf.get('module_default_timeout_sec', 10),
            },
        }
        path = _config_path()
        try:
            with open(path, 'w', encoding='utf-8') as f:
                json.dump(data, f, indent=2, ensure_ascii=False)
            messagebox.showinfo('Guardado', f'Configuración guardada.\n{path}', parent=win)
            win.destroy()
        except Exception as e:
            messagebox.showerror('Error', str(e), parent=win)

    def _all_on():
        for v in checks.values():
            v.set(True)

    def _all_off():
        for v in checks.values():
            v.set(False)

    foot = tk.Frame(win, bg=C['bg_primary'])
    foot.pack(fill=tk.X, padx=16, pady=12)
    tk.Button(foot, text='Activar todos', command=_all_on, bg=C['bg_primary'], fg=C['text_secondary'],
              relief=tk.FLAT).pack(side=tk.LEFT)
    tk.Button(foot, text='Desactivar todos', command=_all_off, bg=C['bg_primary'], fg=C['text_secondary'],
              relief=tk.FLAT).pack(side=tk.LEFT, padx=8)
    tk.Button(foot, text='Guardar', command=_save, bg=C['accent'], fg='#fff',
              relief=tk.FLAT, padx=16, pady=6).pack(side=tk.RIGHT)

    win.bind('<Control-Shift-M>', lambda e: win.destroy())
