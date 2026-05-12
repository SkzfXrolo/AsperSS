from __future__ import annotations


def test_known_cves_regression_placeholder():
    known = ["CVE-placeholder-1", "CVE-placeholder-2"]
    assert len(known) >= 2
