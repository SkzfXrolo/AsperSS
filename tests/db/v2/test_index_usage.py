from __future__ import annotations

import sqlite3


def test_index_usage_smoke():
    con = sqlite3.connect(":memory:")
    cur = con.cursor()
    cur.execute("create table users(id integer primary key, email text)")
    cur.execute("create index idx_users_email on users(email)")
    idx = cur.execute("pragma index_list(users)").fetchall()
    assert any("idx_users_email" in str(r) for r in idx)
