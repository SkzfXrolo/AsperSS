from __future__ import annotations


def test_no_orphans_query_shape():
    child_rows = [{"id": 1, "parent_id": 1}]
    parents = {1}
    assert all(r["parent_id"] in parents for r in child_rows)
