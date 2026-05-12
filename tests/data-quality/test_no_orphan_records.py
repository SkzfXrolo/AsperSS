from __future__ import annotations


def test_no_orphan_records():
    children = [{"parent_id": 1}]
    parents = {1}
    assert all(c["parent_id"] in parents for c in children)
