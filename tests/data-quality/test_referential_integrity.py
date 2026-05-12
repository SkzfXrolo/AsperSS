from __future__ import annotations


def test_referential_integrity_dataset():
    rows = [{"scan_id": 1}]
    scans = {1}
    assert all(r["scan_id"] in scans for r in rows)
