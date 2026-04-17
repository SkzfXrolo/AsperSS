# -*- mode: python ; coding: utf-8 -*-

block_cipher = None

a = Analysis(
    ['main.py'],
    pathex=[],
    binaries=[],
    datas=[
        ('config.json', '.'),
        ('assets/logo.png', 'assets'),   # Logo Argus (se muestra en la UI)
    ],
    hiddenimports=[
        'requests', 'psutil',
        'flask', 'flask_cors',
        'db_integration', 'ai_analyzer', 'astro_ss_techniques', 'silent_scanner_techniques',
        'ui_style', 'mouse_weight_detector', 'ss_forensics',
    ],
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[
        'matplotlib', 'numpy', 'scipy', 'pandas',
    ],
    win_no_prefer_redirects=False,
    win_private_assemblies=False,
    cipher=block_cipher,
    noarchive=False,
)
pyz = PYZ(a.pure, a.zipped_data, cipher=block_cipher)

exe = EXE(
    pyz,
    a.scripts,
    a.binaries,
    a.zipfiles,
    a.datas,
    [],
    name='ArgusScanner',
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=False,
    upx_exclude=[],
    runtime_tmpdir=None,
    console=False,                  # Sin ventana de consola negra
    icon='assets/logo.ico',         # Ícono del exe — poner logo.ico en assets/
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
)
