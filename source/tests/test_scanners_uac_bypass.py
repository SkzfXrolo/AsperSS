import scanners.uac_bypass as s


def test_uac_bypass_returns_list():
    assert isinstance(s.scan_uac_bypass(), list)

