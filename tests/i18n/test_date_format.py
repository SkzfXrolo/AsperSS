from __future__ import annotations

from datetime import datetime

import pytest

format_date = pytest.importorskip("babel.dates").format_date


def test_date_format_per_locale():
    d = datetime(2026, 5, 12)
    assert format_date(d, locale="es").lower()
    assert format_date(d, locale="en").lower()
