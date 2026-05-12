from __future__ import annotations

import sqlite3


def test_unique_constraint_works():
    con = sqlite3.connect(":memory:")
    cur = con.cursor()
    cur.execute("CREATE TABLE users(id INTEGER PRIMARY KEY, email TEXT UNIQUE)")
    cur.execute("INSERT INTO users(email) VALUES ('a@a.com')")
    con.commit()
    assert cur.execute("SELECT COUNT(*) FROM users").fetchone()[0] == 1
