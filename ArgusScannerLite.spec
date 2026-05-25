# -*- mode: python ; coding: utf-8 -*-


a = Analysis(
    ['source\\main_lite.py'],
    pathex=[],
    binaries=[],
    datas=[
        ('source\\assets', 'assets'),
    ],
    hiddenimports=['PIL', 'PIL.Image', 'PIL.ImageTk'],
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=['matplotlib', 'matplotlib.backends', 'matplotlib.figure'],
    noarchive=False,
    optimize=0,
)
pyz = PYZ(a.pure)

exe = EXE(
    pyz,
    a.scripts,
    a.binaries,
    a.datas,
    [],
    name='ArgusScannerLite',
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
    icon='source\\assets\\logo.ico',
)
