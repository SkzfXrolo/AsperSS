# -*- mode: python ; coding: utf-8 -*-
# ArgusAdmin — Control Imperial (.exe)
# python -m PyInstaller ArgusAdmin.spec

import sys
from pathlib import Path

_icon = Path('assets/argus_admin.ico')
_datas = []
if _icon.is_file():
    _datas.append((str(_icon), 'assets'))

a = Analysis(
    ['run_argus_admin.py'],
    pathex=['.'],
    binaries=[],
    datas=_datas,
    hiddenimports=[
        'argus_admin', 'argus_admin.gui', 'argus_admin.voice_lock',
        'argus_admin.api_client', 'argus_admin.config_local',
        'numpy', 'requests',
    ],
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[],
    noarchive=False,
)
pyz = PYZ(a.pure)

_kw = dict(
    name='ArgusAdmin',
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
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
