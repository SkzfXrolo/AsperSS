from __future__ import annotations

import sqlite3

from hypothesis import given, strategies as st


@given(st.text(max_size=20))
def test_db_insert_select_roundtrip(name):
    conn = sqlite3.connect(":memory:")
    cur = conn.cursor()
    cur.execute("CREATE TABLE t (id INTEGER PRIMARY KEY, name TEXT NOT NULL)")
    cur.execute("INSERT INTO t(name) VALUES (?)", (name,))
    cur.execute("SELECT name FROM t WHERE id=1")
    got = cur.fetchone()[0]
    conn.close()
    assert got == name
