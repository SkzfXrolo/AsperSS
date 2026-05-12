import scanners.registry_anomalies as s


def test_registry_returns_list():
    out = s.scan_registry_anomalies()
    assert isinstance(out, list)

