from pathlib import Path


def _txt():
    return Path("source/main.py").read_text(encoding="utf-8", errors="ignore").lower()


def test_has_com_hijack():
    assert "def scan_com_hijacking_registry" in _txt()


def test_has_dll_sideload():
    assert "def scan_dll_sideloading" in _txt()


def test_has_signed_tamper():
    assert "def scan_system_signed_tamper" in _txt()


def test_has_prefetch():
    assert "def scan_prefetch_execution_parser" in _txt()


def test_has_amcache_unique():
    assert "def scan_amcache_unique_sha1" in _txt()


def test_prefetch_versions():
    t = _txt()
    assert "version not in (23, 26, 30)" in t


def test_com_clsid_path():
    assert r"software\classes\clsid" in _txt()


def test_signed_uses_authenticode():
    assert "get-authenticodesignature" in _txt()


def test_amcache_uses_inventory_key():
    assert "inventoryapplicationfile" in _txt()


def test_sideload_names_present():
    assert "winmm.dll" in _txt()

