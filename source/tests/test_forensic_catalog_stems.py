"""Stems del catálogo deben alimentar match_hack_stem."""
from forensic_match import STRONG_STEMS, match_hack_stem


def test_catalog_stems_in_strong():
    # stems_extra de catalog.json 1.8.5
    for stem in ("thunderhack", "myau", "doomsday", "ravenbplus"):
        assert stem in STRONG_STEMS, stem


def test_match_new_stems():
    assert match_hack_stem("ThunderHack-Installer.exe") == "thunderhack"
    assert match_hack_stem("myau-client.jar") == "myau"
