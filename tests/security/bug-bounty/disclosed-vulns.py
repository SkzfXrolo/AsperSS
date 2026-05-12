from __future__ import annotations


def test_disclosed_vulns_placeholder():
    disclosures = ["ASPERS-2026-001"]
    assert disclosures[0].startswith("ASPERS-")
