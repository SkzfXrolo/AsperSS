"""Carga configuración beta de módulos/UI del scanner (scanner_custom.json)."""
import json
import os
import sys

_DEFAULT = {
    'beta_customization': False,
    'modules': {},
    'ui': {'theme': 'cosmic', 'show_splash': True, 'show_wordmark': True},
    'performance': {'module_pool_size': 6, 'module_default_timeout_sec': 10},
}


def _config_path():
    if getattr(sys, 'frozen', False):
        base = os.path.join(os.environ.get('APPDATA', ''), 'ASPERSProjectsSS')
        os.makedirs(base, exist_ok=True)
        return os.path.join(base, 'scanner_custom.json')
    here = os.path.dirname(os.path.abspath(__file__))
    return os.path.join(here, 'scanner_custom.json')


def load_scanner_custom():
    path = _config_path()
    data = dict(_DEFAULT)
    try:
        if os.path.isfile(path):
            with open(path, 'r', encoding='utf-8') as f:
                user = json.load(f) or {}
            for k, v in user.items():
                if isinstance(v, dict) and isinstance(data.get(k), dict):
                    data[k] = {**data[k], **v}
                else:
                    data[k] = v
        if getattr(sys, 'frozen', False):
            try:
                bundled = os.path.join(getattr(sys, '_MEIPASS', ''), 'config', 'scanner_custom.json')
                if os.path.isfile(bundled):
                    with open(bundled, 'r', encoding='utf-8') as f:
                        bundled_data = json.load(f) or {}
                    for k, v in bundled_data.items():
                        if isinstance(v, dict) and isinstance(data.get(k), dict):
                            data[k] = {**data[k], **v}
                        elif k not in data or data[k] in (None, {}, []):
                            data[k] = v
            except Exception:
                pass
        elif not getattr(sys, 'frozen', False):
            bundled = os.path.join(os.path.dirname(path), 'scanner_custom.json')
            if os.path.isfile(bundled):
                with open(bundled, 'r', encoding='utf-8') as f:
                    bundled_data = json.load(f) or {}
                for k, v in bundled_data.items():
                    if k not in data or not data.get(k):
                        data[k] = v
    except Exception as e:
        print(f"[custom] No se pudo cargar scanner_custom.json: {e}")
    return data


def is_module_enabled(custom, module_id, default=True):
    mods = (custom or {}).get('modules') or {}
    if module_id in mods:
        return bool(mods[module_id])
    return default
