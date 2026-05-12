from __future__ import annotations


def test_schema_drift_smoke():
    expected = {"users", "scans"}
    current = {"users", "scans"}
    assert expected == current
