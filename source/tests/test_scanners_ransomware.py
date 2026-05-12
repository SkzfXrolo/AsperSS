from scanners.ransomware_indicators import scan_ransomware_indicators
import tempfile


def test_ransomware_returns_list():
    with tempfile.TemporaryDirectory() as td:
        out = scan_ransomware_indicators(root=td)
    assert isinstance(out, list)

