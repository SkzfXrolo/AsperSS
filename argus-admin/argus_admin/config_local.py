"""Config local (%APPDATA%/ArgusAdmin) — editable por Argus Assistant."""
from __future__ import annotations

import json
import os
import uuid
from pathlib import Path

_DIR = Path(os.environ.get('APPDATA', '.')) / 'ArgusAdmin'
_CONFIG = _DIR / 'config.json'


def config_dir() -> Path:
    _DIR.mkdir(parents=True, exist_ok=True)
    return _DIR


def device_id() -> str:
    cfg = load()
    did = cfg.get('device_id')
    if not did:
        did = str(uuid.uuid4())
        cfg['device_id'] = did
        save(cfg)
    return did


def load() -> dict:
    default = {
        'api_url': 'https://asperss.onrender.com',
        'username': '',
        'phrase': 'desbloqueo argus',
        'device_id': None,
        'voice_threshold': 0.45,
    }
    if not _CONFIG.is_file():
        return default
    try:
        data = json.loads(_CONFIG.read_text(encoding='utf-8'))
        default.update(data)
    except Exception:
        pass
    return default


def save(data: dict) -> None:
    config_dir()
    _CONFIG.write_text(json.dumps(data, indent=2, ensure_ascii=False), encoding='utf-8')


def update(**kwargs) -> dict:
    cfg = load()
    cfg.update(kwargs)
    save(cfg)
    return cfg
