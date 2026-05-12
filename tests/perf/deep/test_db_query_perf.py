from __future__ import annotations

import sqlite3
import time

import pytest


@pytest.mark.perf
def test_db_query_perf_baseline():
    con = sqlite3.connect(":memory:")
    cur = con.cursor()
    cur.execute("create table t(id integer primary key, v text)")
    for i in range(1000):
        cur.execute("insert into t(v) values (?)", (f"v{i}",))
    con.commit()
    start = time.perf_counter()
    cur.execute("select * from t where id = 500").fetchone()
    assert (time.perf_counter() - start) < 0.05
