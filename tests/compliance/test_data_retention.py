from __future__ import annotations

from datetime import datetime, timedelta


def test_data_retention_cutoff_logic():
    now = datetime.utcnow()
    old = now - timedelta(days=400)
    cutoff = now - timedelta(days=365)
    assert old < cutoff
