"""Carga variables de entorno para desarrollo local (web_app/.env.local)."""
from __future__ import annotations

import os
from pathlib import Path

_WEB_APP_DIR = Path(__file__).resolve().parent


def _load_env_file(path: Path) -> None:
    if not path.is_file():
        return
    for raw in path.read_text(encoding='utf-8').splitlines():
        line = raw.strip()
        if not line or line.startswith('#') or '=' not in line:
            continue
        key, _, value = line.partition('=')
        key = key.strip()
        value = value.strip().strip('"').strip("'")
        if key and key not in os.environ:
            os.environ[key] = value


def bootstrap_local_env() -> None:
    """Carga .env.local (y .env) antes de importar el resto de la app."""
    if os.environ.get('RENDER'):
        return
    try:
        from dotenv import load_dotenv
        for name in ('.env.local', '.env'):
            p = _WEB_APP_DIR / name
            if p.is_file():
                load_dotenv(p, override=False)
    except ImportError:
        for name in ('.env.local', '.env'):
            _load_env_file(_WEB_APP_DIR / name)


def is_local_dev() -> bool:
    return os.environ.get('ARGUS_LOCAL_DEV', '').strip().lower() in ('1', 'true', 'yes')
