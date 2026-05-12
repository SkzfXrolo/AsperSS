from __future__ import annotations

import winreg


def safe_open_key(hive, path, access=winreg.KEY_READ):
    try:
        return winreg.OpenKey(hive, path, 0, access)
    except Exception:
        return None


def safe_read_value(key, name, default=None):
    try:
        value, _ = winreg.QueryValueEx(key, name)
        return value
    except Exception:
        return default


def walk_subkeys(key):
    idx = 0
    while True:
        try:
            yield winreg.EnumKey(key, idx)
            idx += 1
        except OSError:
            break

