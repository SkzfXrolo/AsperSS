import scanners.dns_artifacts as d


def test_dns_keys():
    out = d.scan_dns_artifacts()
    assert "dns_cache" in out
    assert "hosts_entries" in out

