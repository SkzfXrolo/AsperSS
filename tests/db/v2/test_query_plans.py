from __future__ import annotations

import sqlite3


def test_query_plan_smoke():
    con = sqlite3.connect(":memory:")
    cur = con.cursor()
    cur.execute("create table t(id integer primary key, v text)")
    plan = cur.execute("explain query plan select * from t where id = 1").fetchall()
    assert len(plan) > 0
