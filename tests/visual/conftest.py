from __future__ import annotations

import hashlib
from pathlib import Path

import pytest


BASELINES = Path("tests/visual/baselines")
ACTUALS = Path("tests/visual/actual")
DIFF_THRESHOLD = 0.001  # 0.1%


def image_hash(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


@pytest.fixture
def visual_dirs():
    BASELINES.mkdir(parents=True, exist_ok=True)
    ACTUALS.mkdir(parents=True, exist_ok=True)
    return BASELINES, ACTUALS
