from __future__ import annotations

import sqlite3


def test_indexes_exist():
    conn = sqlite3.connect(":memory:")
    cur = conn.cursor()
    cur.execute("CREATE TABLE scans (id INTEGER PRIMARY KEY, machine_name TEXT)")
    cur.execute("CREATE INDEX idx_scans_machine_name ON scans(machine_name)")
    cur.execute("PRAGMA index_list('scans')")
    indexes = cur.fetchall()
    conn.close()
    assert any("idx_scans_machine_name" in str(i) for i in indexes)
