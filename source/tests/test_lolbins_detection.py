from pathlib import Path


def _src():
    return Path("source/main.py").read_text(encoding="utf-8", errors="ignore").lower()


def test_has_scan_func():
    assert "def scan_lolbins_extra" in _src()


def test_rule_mshta_remote():
    assert "mshta_remote" in _src()


def test_rule_mshta_js():
    assert "mshta_js" in _src()


def test_rule_regsvr32():
    assert "regsvr32_squiblydoo" in _src()


def test_rule_certutil_decode():
    assert "certutil_decode" in _src()


def test_rule_certutil_urlcache():
    assert "certutil_urlcache" in _src()


def test_rule_bitsadmin():
    assert "bitsadmin_download" in _src()


def test_rule_installutil():
    assert "installutil_exec" in _src()


def test_rule_wmic():
    assert "wmic_process_call_create" in _src()


def test_rule_hh():
    assert "hh_chm" in _src()

