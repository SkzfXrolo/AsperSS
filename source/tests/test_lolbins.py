from pathlib import Path


def test_lolbins_signature_keys_present():
    text = Path("source/main.py").read_text(encoding="utf-8", errors="ignore").lower()
    assert "scan_lolbins_extra" in text
    assert "regsvr32_squiblydoo" in text


def test_lolbins_contains_mshta_rule():
    text = Path("source/main.py").read_text(encoding="utf-8", errors="ignore").lower()
    assert "mshta_remote" in text


def test_lolbins_contains_certutil_rules():
    text = Path("source/main.py").read_text(encoding="utf-8", errors="ignore").lower()
    assert "certutil_decode" in text

