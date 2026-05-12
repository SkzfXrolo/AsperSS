from __future__ import annotations

from datetime import datetime, timedelta


def test_created_before_updated():
    created = datetime.utcnow()
    updated = created + timedelta(seconds=1)
    assert created <= updated
