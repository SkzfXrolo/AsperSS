from scanners.persistence_consolidated import scan_persistence_consolidated


def test_persistence_consolidated_keys():
    out = scan_persistence_consolidated()
    assert "startup_total" in out
    assert "services_total" in out

