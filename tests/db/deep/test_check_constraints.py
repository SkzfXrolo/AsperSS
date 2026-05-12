from __future__ import annotations

import sqlite3


def test_check_constraint_shape():
    con = sqlite3.connect(":memory:")
    cur = con.cursor()
    cur.execute("CREATE TABLE scans(id INTEGER PRIMARY KEY, score REAL CHECK(score >= 0 AND score <= 1))")
    cur.execute("INSERT INTO scans(score) VALUES (0.5)")
    con.commit()
    assert cur.execute("SELECT COUNT(*) FROM scans").fetchone()[0] == 1
