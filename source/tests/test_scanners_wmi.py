import scanners.wmi_subscriptions as w


def test_wmi_keys():
    out = w.scan_wmi_subscriptions()
    assert "filters" in out and "consumers" in out and "bindings" in out

