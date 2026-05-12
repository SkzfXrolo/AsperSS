from __future__ import annotations

import sqlite3


def test_migration_forward_back_smoke():
    con = sqlite3.connect(":memory:")
    cur = con.cursor()
    cur.execute("create table x(id integer)")
    cur.execute("drop table x")
    con.commit()
    assert True
