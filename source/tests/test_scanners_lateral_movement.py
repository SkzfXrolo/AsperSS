from scanners.lateral_movement_indicators import scan_lateral_movement_indicators


def test_lateral_returns_list():
    out = scan_lateral_movement_indicators()
    assert isinstance(out, list)

