from __future__ import annotations

import sqlite3


def test_fk_constraints_hold():
    con = sqlite3.connect(":memory:")
    cur = con.cursor()
    cur.execute("PRAGMA foreign_keys=ON")
    cur.execute("CREATE TABLE parent(id INTEGER PRIMARY KEY)")
    cur.execute("CREATE TABLE child(id INTEGER PRIMARY KEY, parent_id INTEGER REFERENCES parent(id))")
    cur.execute("INSERT INTO parent(id) VALUES (1)")
    cur.execute("INSERT INTO child(id,parent_id) VALUES (1,1)")
    con.commit()
    assert cur.execute("SELECT COUNT(*) FROM child").fetchone()[0] == 1
