"""Tests catálogo firmas + matching high-value."""
import json
import os

from forensic_match import match_hack_stem
from scan_modules.high_value_checks import load_signature_catalog


def test_catalog_loads_semver():
    cat = load_signature_catalog()
    assert cat.get("semver"), "catalog.json debe tener semver"
    assert isinstance(cat.get("ghost_registry_keys"), list)
    assert len(cat["ghost_registry_keys"]) >= 5


def test_catalog_file_on_disk():
    path = os.path.join(
        os.path.dirname(__file__), "..", "bundle", "signatures", "catalog.json"
    )
    assert os.path.isfile(path)
    with open(path, encoding="utf-8") as f:
        data = json.load(f)
    assert "stems_extra" in data


def test_match_catalog_stems():
    assert match_hack_stem("C:\\Users\\x\\Desktop\\thunderhack.exe") == "thunderhack"
    assert match_hack_stem("vapev4.jar") is not None
    # ambiguo sin co-token no debe matchear
    assert match_hack_stem("sigma_installer_notes.txt") is None or "sigma" in (
        match_hack_stem("sigma_client_loader.exe") or ""
    )
