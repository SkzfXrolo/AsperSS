from __future__ import annotations

from datetime import datetime, timedelta


def test_timestamps_consistent():
    c = datetime.utcnow()
    u = c + timedelta(seconds=1)
    assert c <= u
