"""Tests para matching de procesos inyector activos."""
from utils.injector_process import (
    is_injector_process_whitelisted,
    match_injector_process,
)


def test_wallpaper_service_not_injector():
    assert match_injector_process('WallpaperService32.exe') is None
    assert match_injector_process(
        'WallpaperService32.exe',
        r'C:\Windows\System32\WallpaperService32.exe',
    ) is None
    assert is_injector_process_whitelisted('wallpaperservice32.exe')


def test_ce32_suffix_in_service32_not_matched():
    """ce32 como sufijo de 'service32' no debe disparar (FP histórico)."""
    assert match_injector_process('WallpaperService32.exe') is None
    assert match_injector_process('SomeService32.exe') is None


def test_ce32_standalone_matches():
    assert match_injector_process('ce32.exe') == 'ce32'
    assert match_injector_process('CE64.exe') == 'ce64'


def test_cheat_engine_matches():
    assert match_injector_process('cheatengine-x86_64.exe') == 'cheatengine'
    assert match_injector_process('Cheat Engine.exe') == 'cheatengine'


def test_extreme_injector_matches():
    assert match_injector_process('Extreme Injector v3.exe') == 'extremeinjector'


def test_xenos_requires_segment_not_substring():
    assert match_injector_process('xenos.exe') == 'xenos'
    # nombre largo sin segmento xenos aislado
    assert match_injector_process('notxenosapp.exe') is None
