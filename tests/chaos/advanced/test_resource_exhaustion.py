from __future__ import annotations

import pytest


@pytest.mark.chaos
def test_resource_exhaustion_placeholder():
    blob = bytearray(1024 * 64)
    assert len(blob) == 65536
