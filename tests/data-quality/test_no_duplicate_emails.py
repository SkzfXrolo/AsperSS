from __future__ import annotations


def test_no_duplicate_emails():
    emails = ["a@a.com", "b@b.com"]
    assert len(emails) == len(set(emails))
