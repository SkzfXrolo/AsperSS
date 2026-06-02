# -*- mode: python ; coding: utf-8 -*-
# Build: python scripts/prepare_bundle.py && python -m PyInstaller ArgusScanner.spec --noconfirm --distpath dist_60

import sys
import os
from PyInstaller.utils.hooks import collect_submodules, collect_all

_scan_hidden = collect_submodules('scanners') + collect_submodules('scan_modules')

_tcl_datas = []
_tcl_base = os.path.join(getattr(sys, 'base_prefix', ''), 'tcl')
if os.path.isdir(_tcl_base):
    _tcl_datas.append((_tcl_base, 'tcl'))

_extra_datas = []
_extra_binaries = []
_extra_hidden = []
for _pkg in (
    'cryptography', 'PIL', 'certifi', 'pystray', 'win32ctypes', 'psutil',
    'win32api', 'pythoncom', 'win32com', 'win32com.client', 'pywintypes',
    'tkinter', '_tkinter',
):
    try:
        _d, _b, _h = collect_all(_pkg)
        _extra_datas += _d
        _extra_binaries += _b
        _extra_hidden += _h
    except Exception:
        pass

a = Analysis(
    ['main.py'],
    pathex=[],
    binaries=_extra_binaries,
    datas=[
        ('assets', 'assets'),
        ('bundle', 'bundle'),
        ('config', 'config'),
    ] + _extra_datas + _tcl_datas,
    # bundle/ incluye: scanner_db, hash catalog, lexicon, UI PNG, guía HTML, ZIP STORED
    hiddenimports=[
        'PIL', 'PIL.Image', 'PIL.ImageTk', 'PIL._imagingtk',
        'scan_modules', 'scan_modules.executor', 'scan_modules.novel_surfaces',
        'scan_modules.scanner_bridge', 'scan_modules.mining_automation',
        'scan_modules.context', 'scan_modules.extended_checks',
        'scanners', 'scanners._safe_runner', 'ss_forensics',
        'mouse_weight_detector', 'bundle_runtime',
        'config', 'config.scanner_custom', 'config.hack_signatures', 'config.version',
        'config.lite_mode', 'config.scan_paths', 'config.whitelist',
        'scanner_beta_ui', 'scan_report', 'db_integration', 'legitimate_patterns',
        'ai_analyzer', 'file_cache', 'scoring_system', 'autoclicker_detector',
        'xray_texture_analyzer', 'java_injection_detector', 'ui_enhancements', 'ui_style',
        'requests', 'urllib3', 'certifi', 'charset_normalizer', 'idna',
    ] + _scan_hidden + _extra_hidden,
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=['matplotlib', 'numpy', 'pandas', 'scipy', 'pytest', 'IPython', 'torch', 'tensorflow'],
    noarchive=True,
    optimize=0,
)
pyz = PYZ(a.pure)

exe = EXE(
    pyz,
    a.scripts,
    a.binaries,
    a.datas,
    [],
    name='ArgusScanner',
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
