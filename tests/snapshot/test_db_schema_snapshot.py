from __future__ import annotations

import sqlite3


def test_db_schema_snapshot(snapshot):
    conn = sqlite3.connect(":memory:")
    cur = conn.cursor()
    cur.execute("CREATE TABLE users (id INTEGER PRIMARY KEY, username TEXT UNIQUE NOT NULL)")
    cur.execute("CREATE TABLE scans (id INTEGER PRIMARY KEY, user_id INTEGER, FOREIGN KEY(user_id) REFERENCES users(id))")
    cur.execute("SELECT name, sql FROM sqlite_master WHERE type='table' ORDER BY name")
    schema = cur.fetchall()
    conn.close()
    assert schema == snapshot
