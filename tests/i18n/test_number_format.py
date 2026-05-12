from __future__ import annotations

import pytest

format_decimal = pytest.importorskip("babel.numbers").format_decimal


def test_number_format_per_locale():
    n = 12345.67
    assert "," in format_decimal(n, locale="en_US")
    assert "." in format_decimal(n, locale="es_AR")
