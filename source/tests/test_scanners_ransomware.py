from scanners.ransomware_indicators import scan_ransomware_indicators


def test_ransomware_returns_list():
    out = scan_ransomware_indicators(root="C:\\")
    assert isinstance(out, list)

