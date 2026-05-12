from scanners.anti_forensics import scan_anti_forensics


def test_anti_forensics_returns_list():
    out = scan_anti_forensics()
    assert isinstance(out, list)

