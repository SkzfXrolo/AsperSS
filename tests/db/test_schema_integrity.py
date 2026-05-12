from __future__ import annotations

import sqlite3


def test_schema_integrity_constraints():
    conn = sqlite3.connect(":memory:")
    cur = conn.cursor()
    cur.execute("PRAGMA foreign_keys = ON")
    cur.execute("CREATE TABLE users (id INTEGER PRIMARY KEY, username TEXT UNIQUE NOT NULL)")
    cur.execute("CREATE TABLE scans (id INTEGER PRIMARY KEY, user_id INTEGER NOT NULL, FOREIGN KEY(user_id) REFERENCES users(id))")
    cur.execute("INSERT INTO users(username) VALUES ('u1')")
    cur.execute("INSERT INTO scans(user_id) VALUES (1)")
    conn.close()
    assert True
