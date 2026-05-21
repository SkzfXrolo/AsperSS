# -*- mode: python ; coding: utf-8 -*-
# ArgusAdmin — Control Imperial (.exe)
# python -m PyInstaller ArgusAdmin.spec --noconfirm

from pathlib import Path
from PyInstaller.utils.hooks import collect_all

_icon = Path('assets/argus_admin.ico')
_datas = []
if _icon.is_file():
    _datas.append((str(_icon), 'assets'))

_binaries = []
_hidden = [
    'argus_admin', 'argus_admin.gui', 'argus_admin.voice_lock',
    'argus_admin.api_client', 'argus_admin.config_local', 'argus_admin.main',
    'numpy', 'requests', 'sounddevice', '_sounddevice_data', 'wave',
]
for pkg in ('sounddevice',):
    try:
        d, b, h = collect_all(pkg)
        _datas += d
        _binaries += b
        _hidden += h
    except Exception:
        pass

a = Analysis(
    ['run_argus_admin.py'],
    pathex=['.'],
    binaries=_binaries,
    datas=_datas,
    hiddenimports=_hidden,
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[
        'speech_recognition', 'google', 'grpc', 'tensorflow', 'torch',
        'matplotlib', 'pandas', 'PIL', 'pygments', 'rich', 'anyio',
    ],
    noarchive=False,
)
pyz = PYZ(a.pure)

_kw = dict(
    name='ArgusAdmin',
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=False,
    upx_exclude=[],
    runtime_tmpdir=None,
    console=False,
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
)
if _icon.is_file():
    _kw['icon'] = str(_icon)

exe = EXE(
    pyz,
    a.scripts,
    a.binaries,
    a.datas,
    [],
    **_kw,
)
