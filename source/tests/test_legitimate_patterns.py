"""Tests para whitelist de mods MC y rutas de confianza."""
import os

from legitimate_patterns import LegitimatePatterns


def test_known_mc_mod_by_prefix():
    lp = LegitimatePatterns(database_path=os.devnull)
    ok, conf = lp.is_legitimate(
        r"C:\Users\test\AppData\Roaming\.minecraft\mods\sodium-0.5.8.jar",
        file_name="sodium-0.5.8.jar",
    )
    assert ok is True
    assert conf >= 0.5


def test_unknown_mod_in_mods_not_auto_legit():
    """Ruta mods sola ya no whitelistea JARs con nombre desconocido."""
    lp = LegitimatePatterns(database_path=os.devnull)
    ok, conf = lp.is_legitimate(
        r"C:\Users\test\AppData\Roaming\.minecraft\mods\unknown-mod-1.0.jar",
        file_name="unknown-mod-1.0.jar",
    )
    assert ok is False
    assert conf < 0.5


def test_vape_in_mods_folder_not_legit():
    lp = LegitimatePatterns(database_path=os.devnull)
    ok, conf = lp.is_legitimate(
        r"C:\Users\test\AppData\Roaming\.minecraft\mods\vape.jar",
        file_name="vape.jar",
    )
    assert ok is False
    assert conf == 0.0


def test_path_normalization_forward_slashes():
    lp = LegitimatePatterns(database_path=os.devnull)
    ok, _ = lp.is_legitimate(
        "C:/Users/test/AppData/Roaming/.minecraft/mods/iris-fabric.jar",
        file_name="iris-fabric.jar",
    )
    assert ok is True


def test_hack_jar_not_whitelisted_by_name_alone():
    """Nombre de hack sin ruta de mods ni prefijo conocido → no legítimo."""
    lp = LegitimatePatterns(database_path=os.devnull)
    ok, conf = lp.is_legitimate(
        r"C:\Users\test\Downloads\vape.jar",
        file_name="vape.jar",
    )
    assert ok is False
    assert conf < 0.5


def test_trusted_wallpaper_process_in_context():
    lp = LegitimatePatterns(database_path=os.devnull)
    ok, conf = lp.is_legitimate(
        r"C:\Windows\System32\WallpaperService32.exe",
        file_name="WallpaperService32.exe",
        context={'related_processes': ['WallpaperService32.exe']},
    )
    assert ok is True
    assert conf >= 0.5


def test_rubidium_mod_prefix():
    lp = LegitimatePatterns(database_path=os.devnull)
    ok, conf = lp.is_legitimate(
        r"D:\Games\minecraft\mods\rubidium-0.7.1.jar",
        file_name="rubidium-0.7.1.jar",
    )
    assert ok is True
    assert conf >= 0.5
