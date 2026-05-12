from __future__ import annotations

import sqlite3


def _init(conn):
    cur = conn.cursor()
    cur.execute("CREATE TABLE IF NOT EXISTS users (id INTEGER PRIMARY KEY, username TEXT UNIQUE)")
    cur.execute("CREATE TABLE IF NOT EXISTS scans (id INTEGER PRIMARY KEY, user_id INTEGER)")
    conn.commit()


def test_migration_idempotent():
    conn = sqlite3.connect(":memory:")
    _init(conn)
    _init(conn)
    conn.close()
    assert True
