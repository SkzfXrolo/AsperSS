from scanners.cryptojacking import scan_cryptojacking


def test_cryptojacking_returns_list():
    out = scan_cryptojacking(cpu_threshold=1000)
    assert isinstance(out, list)

