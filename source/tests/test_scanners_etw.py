from scanners.etw_consumers import scan_etw_consumers


def test_etw_keys():
    out = scan_etw_consumers()
    assert "suspicious" in out

